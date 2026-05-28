# Alert processed input --> lee "id", "ttps", "alert_type"
# y los tres maximos CVSS-derived desde la salida anterior del translator cuando se ejecuta por webhook.
#
# Si alert_type = expose, entonces Goal = Expose.
# Si alert_type = affect, entonces Goal = Affect.
# Si alert_type = elicit, entonces Goal = Elicit.
#
# Usa MITRE/activity_exposure_scores.json para aÃ±adir CVSS-derived exposure.
#
# IMPORTANTE:
# Las Activities NO se eliminan por riesgo.
# Todas salen en el output con:
#   - activity_exposure
#   - recommendation.status = recommended | not_recommended

import json
import re
import time 
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# =========================
# APP PATHS
# =========================
APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent

MITRE_DIR = PROJECT_DIR / "MITRE"

GOAL_DETAILS_PATH = MITRE_DIR / "goal_details.json"
APPROACH_DETAILS_PATH = MITRE_DIR / "approach_details.json"
ACTIVITY_DETAILS_PATH = MITRE_DIR / "activity_details.json"
GOAL_APPROACH_MAPPINGS_PATH = MITRE_DIR / "goal_approach_mappings.json"
APPROACH_ACTIVITY_MAPPINGS_PATH = MITRE_DIR / "approach_activity_mappings.json"
ATTACK_MAPPING_PATH = MITRE_DIR / "attack_mapping.json"
EXPOSURE_SCORES_PATH = MITRE_DIR / "activity_exposure_scores.json"


# =========================
# CONSTANTS
# =========================
TTP_PATTERN = re.compile(r"T\d{4}(?:\.\d{3})?", re.IGNORECASE)

GOAL_BY_ALERT_TYPE = {
    "expose": "EGO0001",  # Expose
    "affect": "EGO0002",  # Affect
    "elicit": "EGO0003",  # Elicit
}

REQUIRED_SCORE_FIELDS = [
    "max_cvss_base_score",
    "max_impact_subscore",
    "max_exploitability_subscore",
]


# =========================
# JSON HELPERS
# =========================
def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


# =========================
# GENERIC HELPERS
# =========================
def normalize_to_list(value: Any) -> List[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def flatten_list(values: List[Any]) -> List[Any]:
    flattened = []

    for value in values:
        if isinstance(value, list):
            flattened.extend(value)
        else:
            flattened.append(value)

    return flattened


def unique_preserve_order(values: List[str]) -> List[str]:
    output = []
    seen = set()

    for value in values:
        if value and value not in seen:
            output.append(value)
            seen.add(value)

    return output


def get_first_existing_value(data: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in data:
            return data[key]

    return None


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


# =========================
# ALERT HELPERS
# =========================
def normalize_ttps(value: Any) -> List[str]:
    """
    Normaliza tÃ©cnicas ATT&CK.

    Soporta:
      "T1059.001"
      ["T1020", "T1041"]
      {"id": "T1083"}
      "attack.t1059.001"
    """
    if value is None:
        return []

    values: List[str] = []

    if isinstance(value, dict):
        for key in ("ttps", "ttp", "attack_id", "technique_id", "mitre_id", "id"):
            values.extend(normalize_ttps(value.get(key)))

    elif isinstance(value, list):
        for item in value:
            values.extend(normalize_ttps(item))

    else:
        raw_value = str(value).strip()
        matches = TTP_PATTERN.findall(raw_value)

        if matches:
            values.extend(matches)
        elif raw_value:
            values.append(raw_value)

    normalized_values = []

    for item in values:
        normalized = str(item).strip().upper()

        if normalized.startswith("ATTACK."):
            normalized = normalized.replace("ATTACK.", "", 1)

        if normalized:
            normalized_values.append(normalized)

    return unique_preserve_order(normalized_values)


def normalize_alert_type(value: Any) -> str:
    if value is None:
        raise ValueError("Missing alert_type in translator output.")

    alert_type = str(value).strip().lower()

    if alert_type not in GOAL_BY_ALERT_TYPE:
        raise ValueError(
            f"Unsupported alert_type '{value}'. "
            f"Expected one of: {sorted(GOAL_BY_ALERT_TYPE)}"
        )

    return alert_type


def normalize_score_fields(alert: Dict[str, Any]) -> Dict[str, float]:
    normalized = {}

    for field in REQUIRED_SCORE_FIELDS:
        if field not in alert:
            raise ValueError(f"Missing {field} in translator output.")

        try:
            normalized[field] = float(alert[field])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid {field}: expected numeric value, got {alert[field]!r}"
            ) from exc

    return normalized


def ttp_lookup_keys(ttp: str) -> List[str]:
    """
    Si viene una subtÃ©cnica, prueba tambiÃ©n la tÃ©cnica padre.

    Ejemplo:
      T1059.001 -> ["T1059.001", "T1059"]
    """
    keys = [ttp]

    if "." in ttp:
        keys.append(ttp.split(".", 1)[0])

    return keys


def select_alert(
    alerts: List[Dict[str, Any]],
    alert_id: Optional[int],
) -> Dict[str, Any]:
    """
    Si alert_id existe, selecciona por id incremental asignado por translator.py.
    Si alert_id no existe, selecciona la Ãºltima alerta acumulada.
    """
    if not alerts:
        raise ValueError("No alerts found in translator output.")

    if alert_id is None:
        return alerts[-1]

    for alert in alerts:
        try:
            current_id = int(alert.get("id"))
        except (TypeError, ValueError):
            continue

        if current_id == alert_id:
            return alert

    available_ids = [
        alert.get("id")
        for alert in alerts
        if "id" in alert
    ]

    raise ValueError(
        f"Alert id {alert_id} not found. Available ids: {available_ids}"
    )


# =========================
# MITRE DETAIL HELPERS
# =========================
def get_detail(details: Any, item_id: str) -> Dict[str, Any]:
    """
    Soporta detalles en formato diccionario:

      {
        "EGO0001": {
          "name": "Expose"
        }
      }

    y en formato lista:

      [
        {
          "id": "EGO0001",
          "name": "Expose"
        }
      ]
    """
    if isinstance(details, dict):
        value = details.get(item_id)

        if isinstance(value, dict):
            return value

        for value in details.values():
            if not isinstance(value, dict):
                continue

            candidate_id = get_first_existing_value(
                value,
                [
                    "id",
                    "goal_id",
                    "approach_id",
                    "activity_id",
                    "ego_id",
                    "eap_id",
                    "eac_id",
                ],
            )

            if candidate_id == item_id:
                return value

    if isinstance(details, list):
        for item in details:
            if not isinstance(item, dict):
                continue

            candidate_id = get_first_existing_value(
                item,
                [
                    "id",
                    "goal_id",
                    "approach_id",
                    "activity_id",
                    "ego_id",
                    "eap_id",
                    "eac_id",
                ],
            )

            if candidate_id == item_id:
                return item

    return {}


def extract_ids_from_mapping(
    mapping_data: Any,
    source_id: str,
    source_keys: List[str],
    target_keys: List[str],
) -> List[str]:
    """
    Extrae IDs desde ficheros de mapping.

    Soporta diccionarios:

      {
        "EGO0001": ["EAP0001", "EAP0002"]
      }

      {
        "EGO0001": {
          "approaches": ["EAP0001"]
        }
      }

    Soporta listas:

      [
        {
          "goal_id": "EGO0001",
          "approach_id": "EAP0001"
        },
        {
          "goal_id": "EGO0001",
          "approaches": ["EAP0001", "EAP0002"]
        }
      ]
    """
    collected: List[str] = []

    if isinstance(mapping_data, dict):
        direct_value = mapping_data.get(source_id)

        if isinstance(direct_value, list):
            collected.extend(
                str(item).strip()
                for item in direct_value
                if item
            )

        elif isinstance(direct_value, dict):
            for target_key in target_keys:
                collected.extend(
                    str(item).strip()
                    for item in normalize_to_list(direct_value.get(target_key))
                    if item
                )

        for item in mapping_data.values():
            if not isinstance(item, dict):
                continue

            source_value = get_first_existing_value(item, source_keys)

            if source_value != source_id:
                continue

            for target_key in target_keys:
                collected.extend(
                    str(value).strip()
                    for value in normalize_to_list(item.get(target_key))
                    if value
                )

    elif isinstance(mapping_data, list):
        for item in mapping_data:
            if not isinstance(item, dict):
                continue

            source_value = get_first_existing_value(item, source_keys)

            if source_value != source_id:
                continue

            for target_key in target_keys:
                collected.extend(
                    str(value).strip()
                    for value in normalize_to_list(item.get(target_key))
                    if value
                )

    return unique_preserve_order(collected)


def get_goal_approach_ids(
    goal_id: str,
    goal_details: Any,
    goal_approach_mappings: Any,
) -> List[str]:
    """
    Prioridad:
      1. MITRE/goal_approach_mappings.json
      2. Campo "approaches" embebido en goal_details.json
    """
    approach_ids = extract_ids_from_mapping(
        mapping_data=goal_approach_mappings,
        source_id=goal_id,
        source_keys=["goal_id", "ego_id", "goal", "id"],
        target_keys=["approach_id", "eap_id", "approach", "approaches"],
    )

    if approach_ids:
        return approach_ids

    goal = get_detail(goal_details, goal_id)

    return [
        str(item).strip()
        for item in normalize_to_list(goal.get("approaches"))
        if item
    ]


def get_approach_activity_ids(
    approach_id: str,
    approach_details: Any,
    approach_activity_mappings: Any,
) -> List[str]:
    """
    Prioridad:
      1. MITRE/approach_activity_mappings.json
      2. Campo "activities" embebido en approach_details.json
    """
    activity_ids = extract_ids_from_mapping(
        mapping_data=approach_activity_mappings,
        source_id=approach_id,
        source_keys=["approach_id", "eap_id", "approach", "id"],
        target_keys=["activity_id", "eac_id", "activity", "activities"],
    )

    if activity_ids:
        return activity_ids

    approach = get_detail(approach_details, approach_id)

    return [
        str(item).strip()
        for item in normalize_to_list(approach.get("activities"))
        if item
    ]


# =========================
# ATT&CK -> ACTIVITY MAPPING
# =========================
def build_ttp_to_activities(attack_mapping: Any) -> Dict[str, Set[str]]:
    """
    Construye Ã­ndice:

      T1020 -> {EAC0002, EAC0016, ...}

    Soporta entradas como:

      {
        "attack_id": "T1020",
        "eac_id": "EAC0002"
      }

    o:

      {
        "attack_ids": ["T1020", "T1041"],
        "activities": ["EAC0002", "EAC0016"]
      }
    """
    index: Dict[str, Set[str]] = {}

    if isinstance(attack_mapping, dict):
        iterable = attack_mapping.values()
    elif isinstance(attack_mapping, list):
        iterable = attack_mapping
    else:
        iterable = []

    for item in iterable:
        if not isinstance(item, dict):
            continue

        attack_ids = normalize_ttps(
            get_first_existing_value(
                item,
                [
                    "attack_id",
                    "attack_ids",
                    "ttp",
                    "ttps",
                    "mitre_id",
                    "technique_id",
                ],
            )
        )

        activity_ids = normalize_to_list(
            get_first_existing_value(
                item,
                [
                    "eac_id",
                    "activity_id",
                    "activity_ids",
                    "activities",
                ],
            )
        )

        for attack_id in attack_ids:
            for activity_id in activity_ids:
                if attack_id and activity_id:
                    index.setdefault(attack_id, set()).add(
                        str(activity_id).strip()
                    )

    return index


def get_activity_ids_for_ttps(
    ttps: List[str],
    ttp_to_activities: Dict[str, Set[str]],
) -> Set[str]:
    """
    Une las Activities asociadas a todas las TTPs.

    Si una TTP es subtÃ©cnica y no existe en attack_mapping.json,
    intenta tambiÃ©n con la tÃ©cnica padre.
    """
    activity_ids: Set[str] = set()

    for ttp in ttps:
        for lookup_key in ttp_lookup_keys(ttp):
            activity_ids.update(ttp_to_activities.get(lookup_key, set()))

    return activity_ids


# =========================
# EXPOSURE SCORES
# =========================
def exposure_pair_key(approach_name: Any, activity_name: Any) -> str:
    """
    La exposiciÃ³n depende del par Approach / Activity.
    """
    return f"{normalize_text(approach_name)}::{normalize_text(activity_name)}"


def build_exposure_lookup(exposure_data: Any) -> Dict[str, Dict[str, Any]]:
    """
    Construye Ã­ndice:

      "collect::api monitoring" -> {
        "cvss_vector": "...",
        "cvss_base_score": 2.5,
        "impact_subscore": 1.4,
        "exploitability_subscore": 1.0
      }
    """
    if isinstance(exposure_data, dict):
        entries = exposure_data.get("entries", [])
    elif isinstance(exposure_data, list):
        entries = exposure_data
    else:
        entries = []

    lookup: Dict[str, Dict[str, Any]] = {}

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        approach = entry.get("approach")
        activity = entry.get("activity")

        if not approach or not activity:
            continue

        try:
            exposure = {
                "cvss_vector": entry.get("cvss_vector"),
                "cvss_base_score": float(entry["cvss_base_score"]),
                "impact_subscore": float(entry["impact_subscore"]),
                "exploitability_subscore": float(entry["exploitability_subscore"]),
            }
        except KeyError as exc:
            raise ValueError(
                f"Missing exposure field in activity_exposure_scores.json entry: {entry}"
            ) from exc
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid numeric exposure score in activity_exposure_scores.json entry: {entry}"
            ) from exc

        key = exposure_pair_key(approach, activity)
        lookup[key] = exposure

    return lookup


def get_activity_exposure_for_pair(
    exposure_lookup: Dict[str, Dict[str, Any]],
    approach_name: Any,
    activity_name: Any,
) -> Optional[Dict[str, Any]]:
    key = exposure_pair_key(approach_name, activity_name)
    return exposure_lookup.get(key)


# =========================
# RECOMMENDATION LOGIC
# =========================
def evaluate_activity_recommendation(
    activity_exposure: Optional[Dict[str, Any]],
    score_fields: Dict[str, float],
) -> Dict[str, Any]:
    """
    EvalÃºa si una Activity es recomendable segÃºn los tres mAximos configurados.

    La Activity nunca se elimina. Solo se marca como:
      - recommended
      - not_recommended
    """
    if activity_exposure is None:
        return {
            "status": "not_recommended",
            "reason": "missing activity exposure scores",
        }

    exceeded_fields = []

    if activity_exposure["cvss_base_score"] > score_fields["max_cvss_base_score"]:
        exceeded_fields.append("cvss_base_score")

    if activity_exposure["impact_subscore"] > score_fields["max_impact_subscore"]:
        exceeded_fields.append("impact_subscore")

    if (
        activity_exposure["exploitability_subscore"]
        > score_fields["max_exploitability_subscore"]
    ):
        exceeded_fields.append("exploitability_subscore")

    if exceeded_fields:
        return {
            "status": "not_recommended",
            "reason": "exceeds configured maximums",
            "exceeded_fields": exceeded_fields,
        }

    return {
        "status": "recommended",
        "reason": "within configured maximums",
    }


def build_activity_output(
    activity_id: str,
    activity: Dict[str, Any],
    activity_exposure: Optional[Dict[str, Any]],
    score_fields: Dict[str, float],
) -> Dict[str, Any]:
    """
    Construye la salida de una Activity.

    Incluye:
      - exposure real del par Approach / Activity
      - recommended / not_recommended
    """
    return {
        "activity_id": activity_id,
        "activity_name": activity.get("name"),
        "activity_description": activity.get("description"),
        "activity_exposure": activity_exposure,
        "recommendation": evaluate_activity_recommendation(
            activity_exposure=activity_exposure,
            score_fields=score_fields,
        ),
    }


# =========================
# ENGAGE MAPPING
# =========================
def map_alert_to_engage(alert: Dict[str, Any], debug: bool = False) -> Dict[str, Any]:
    goal_details = load_json(GOAL_DETAILS_PATH)
    approach_details = load_json(APPROACH_DETAILS_PATH)
    activity_details = load_json(ACTIVITY_DETAILS_PATH)
    goal_approach_mappings = load_json(GOAL_APPROACH_MAPPINGS_PATH)
    approach_activity_mappings = load_json(APPROACH_ACTIVITY_MAPPINGS_PATH)
    attack_mapping = load_json(ATTACK_MAPPING_PATH)
    exposure_scores = load_json(EXPOSURE_SCORES_PATH)

    exposure_lookup = build_exposure_lookup(exposure_scores)

    alert_id = alert.get("id")
    alert_type = normalize_alert_type(alert.get("alert_type"))
    score_fields = normalize_score_fields(alert)
    ttps = normalize_ttps(alert.get("ttps"))

    goal_id = GOAL_BY_ALERT_TYPE[alert_type]
    goal = get_detail(goal_details, goal_id)

    approach_ids = get_goal_approach_ids(
        goal_id=goal_id,
        goal_details=goal_details,
        goal_approach_mappings=goal_approach_mappings,
    )

    ttp_to_activities = build_ttp_to_activities(attack_mapping)
    ttp_activity_ids = get_activity_ids_for_ttps(ttps, ttp_to_activities)

    approaches_output = []
    missing_exposure_scores = []
    recommended_activity_ids = []
    not_recommended_activity_ids = []

    for approach_id in approach_ids:
        approach = get_detail(approach_details, approach_id)
        approach_name = approach.get("name")

        approach_activity_ids = set(
            get_approach_activity_ids(
                approach_id=approach_id,
                approach_details=approach_details,
                approach_activity_mappings=approach_activity_mappings,
            )
        )

        if ttps and ttp_activity_ids:
            selected_activity_ids = sorted(
                approach_activity_ids.intersection(ttp_activity_ids)
            )
        elif ttps and not ttp_activity_ids:
            selected_activity_ids = []
        else:
            selected_activity_ids = sorted(approach_activity_ids)

        activities_output = []

        for activity_id in selected_activity_ids:
            activity = get_detail(activity_details, activity_id)
            activity_name = activity.get("name")

            activity_exposure = get_activity_exposure_for_pair(
                exposure_lookup=exposure_lookup,
                approach_name=approach_name,
                activity_name=activity_name,
            )

            if activity_exposure is None:
                missing_exposure_scores.append(
                    {
                        "approach_id": approach_id,
                        "approach_name": approach_name,
                        "activity_id": activity_id,
                        "activity_name": activity_name,
                    }
                )

            activity_output = build_activity_output(
                activity_id=activity_id,
                activity=activity,
                activity_exposure=activity_exposure,
                score_fields=score_fields,
            )

            if activity_output["recommendation"]["status"] == "recommended":
                recommended_activity_ids.append(activity_id)
            else:
                not_recommended_activity_ids.append(activity_id)

            activities_output.append(activity_output)

        if not activities_output:
            continue

        approaches_output.append(
            {
                "approach_id": approach_id,
                "approach_name": approach_name,
                "approach_description": approach.get("description"),
                "activities": activities_output,
            }
        )

    result = {
        "MITRE Engage recommendation": {
            "input_alert_id": alert_id,
            "input_alert_name": alert.get("name"),
            "goal_id": goal_id,
            "goal_name": goal.get("name"),
            "goal_description": goal.get("description"),
            "max_cvss_base_score": score_fields["max_cvss_base_score"],
            "max_impact_subscore": score_fields["max_impact_subscore"],
            "max_exploitability_subscore": score_fields["max_exploitability_subscore"],
            "approaches": approaches_output,
        },
    }

    if debug:
        result["input_alert"] = {
            "id": alert_id,
            "name": alert.get("name"),
            "description": alert.get("description"),
            "ttps": ttps,
            "alert_type": alert_type,
            "max_cvss_base_score": score_fields["max_cvss_base_score"],
            "max_impact_subscore": score_fields["max_impact_subscore"],
            "max_exploitability_subscore": score_fields["max_exploitability_subscore"],
            "payload_context": alert.get("payload_context"),
        }

        result["debug"] = {
            "matched_activity_ids_from_ttps": sorted(ttp_activity_ids),
            "recommended_activity_ids": unique_preserve_order(recommended_activity_ids),
            "not_recommended_activity_ids": unique_preserve_order(
                not_recommended_activity_ids
            ),
            "missing_exposure_scores": missing_exposure_scores,
            "used_parent_lookup_for_subtechniques": [
                {
                    "subtechnique": ttp,
                    "parent": ttp.split(".", 1)[0],
                }
                for ttp in ttps
                if "." in ttp
            ],
        }

    return result


# =========================
# WEBHOOK ENTRYPOINT
# =========================
def run_engage_mapper_from_collection(
    alert_collection: Any,
    alert_id: Optional[int] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    time.sleep(5) # Simula tiempo de espera para recibir datos por webhook
    if isinstance(alert_collection, dict) and isinstance(alert_collection.get("Normalized alerts"), list):
        alerts = [
            alert
            for alert in alert_collection["Normalized alerts"]
            if isinstance(alert, dict)
        ]
    elif isinstance(alert_collection, dict) and isinstance(alert_collection.get("alerts"), list):
        alerts = [
            alert
            for alert in alert_collection["alerts"]
            if isinstance(alert, dict)
        ]
    elif isinstance(alert_collection, list):
        alerts = [
            alert
            for alert in alert_collection
            if isinstance(alert, dict)
        ]
    elif isinstance(alert_collection, dict):
        alerts = [alert_collection]
    else:
        raise ValueError("Invalid normalized alert collection.")

    alert = select_alert(
        alerts=alerts,
        alert_id=alert_id,
    )

    return map_alert_to_engage(
        alert=alert,
        debug=debug,
    )


if __name__ == "__main__":
    raise SystemExit("engage_mapper.py now expects translator output through the webhook.")
