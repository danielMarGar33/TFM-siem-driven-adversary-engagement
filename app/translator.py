import json
import re
import time
from typing import Any, Dict, List, Optional


NORMALIZED_ALERT_FIELDS = [
    "id",
    "name",
    "description",
    "ttps",
    "alert_type",
    "max_cvss_base_score",
    "max_impact_subscore",
    "max_exploitability_subscore",
    "payload_context",
]

VALID_ALERT_TYPES = {
    "expose",
    "affect",
    "elicit",
}

REQUIRED_SCORE_FIELDS = [
    "max_cvss_base_score",
    "max_impact_subscore",
    "max_exploitability_subscore",
]

TTP_PATTERN = re.compile(r"T\d{4}(?:\.\d{3})?", re.IGNORECASE)


# =========================
# JSON HELPERS
# =========================
def parse_alert_content(raw_content: str) -> Any:
    raw_content = raw_content.strip()

    if not raw_content:
        return []

    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        alerts = []

        for line_number, line in enumerate(raw_content.splitlines(), start=1):
            line = line.strip()

            if not line:
                continue

            try:
                alerts.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON/NDJSON input at line {line_number}: {exc}"
                ) from exc

        return alerts


def get_next_alert_id(existing_alerts: List[Dict[str, Any]]) -> int:
    """
    Return the next incremental translator-assigned alert id.
    """
    max_id = 0

    for alert in existing_alerts:
        try:
            alert_id = int(alert.get("id", 0))
        except (TypeError, ValueError):
            alert_id = 0

        if alert_id > max_id:
            max_id = alert_id

    return max_id + 1


# =========================
# EXTRACTION HELPERS
# =========================
def get_nested_value(data: Any, path: Optional[str]) -> Any:
    """
    Resolve dot notation paths such as:
      - rule.description
      - rule.mitre.id
      - tags.engage.alert_type

    Also supports flattened keys that already contain dots, for example
    "attack.t1003" at the current object level.
    """
    if data is None or not path:
        return None

    if isinstance(data, dict) and path in data:
        return data[path]

    parts = path.split(".")
    current = data

    for index, part in enumerate(parts):
        remaining_path = ".".join(parts[index:])

        if isinstance(current, dict):
            if remaining_path in current:
                return current[remaining_path]

            current = current.get(part)

        elif isinstance(current, list):
            values = [
                get_nested_value(item, remaining_path)
                for item in current
            ]
            values = [
                value
                for value in values
                if value is not None
            ]

            return values if values else None

        else:
            return None

        if current is None:
            return None

    return current


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


def normalize_ttps(value: Any) -> List[str]:
    """
    Normalize ATT&CK technique IDs into a deterministic de-duplicated list.

    It accepts:
      - plain values such as "T1003" or "attack.t1003.001"
      - nested containers
      - objects whose keys embed ATT&CK IDs
    """
    normalized = []
    seen = set()

    for item in flatten_list(normalize_to_list(value)):
        if item is None:
            continue

        if isinstance(item, dict):
            for key, nested_value in item.items():
                if isinstance(key, str):
                    for technique in TTP_PATTERN.findall(key):
                        normalized_technique = technique.strip().upper()

                        if normalized_technique not in seen:
                            normalized.append(normalized_technique)
                            seen.add(normalized_technique)

                for technique in normalize_ttps(nested_value):
                    if technique not in seen:
                        normalized.append(technique)
                        seen.add(technique)

            continue

        if isinstance(item, list):
            for technique in normalize_ttps(item):
                if technique not in seen:
                    normalized.append(technique)
                    seen.add(technique)

            continue

        for technique in TTP_PATTERN.findall(str(item).strip()):
            normalized_technique = technique.strip().upper()

            if normalized_technique not in seen:
                normalized.append(normalized_technique)
                seen.add(normalized_technique)

    return normalized


def extract_ttps_from_prefixed_keys(data: Any, path: str) -> List[Any]:
    """
    Extract ATT&CK techniques from flattened SIEM keys such as:
      - attack.t1003
      - attack.t1003.001
      - attack.t1055
      - mitre.t1003
    """
    if not path:
        return []

    parent_path, separator, prefix = path.rpartition(".")
    container = get_nested_value(data, parent_path) if separator else data

    if not isinstance(container, dict):
        return []

    prefix_pattern = f"{prefix}."
    values = []

    for key, value in container.items():
        if not isinstance(key, str) or not key.startswith(prefix_pattern):
            continue

        values.append(key[len(prefix_pattern):])
        values.append(value)

    return values


def extract_ttps(alert: Dict[str, Any], mapping_value: Any) -> List[str]:
    """
    Resolve ATT&CK techniques from one or more mapping entries.

    Each entry can point to:
      - a standard nested field such as rule.mitre.id
      - a container object with technique keys such as attack.{t1003,t1055}
      - a flattened SIEM prefix such as attack or mitre
    """
    values = []

    for path in flatten_list(normalize_to_list(mapping_value)):
        if not path:
            continue

        normalized_path = str(path).strip()

        if not normalized_path:
            continue

        resolved_value = get_nested_value(alert, normalized_path)

        if resolved_value is not None:
            values.append(resolved_value)

        values.extend(extract_ttps_from_prefixed_keys(alert, normalized_path))

    return normalize_ttps(values)


def extract_payload_context(
    alert: Dict[str, Any],
    payload_paths: Any,
) -> List[Dict[str, Any]]:
    """
    Preserve operational evidence in payload_context.

    These fields are not promoted to root-level normalized fields.
    """
    if isinstance(payload_paths, str):
        payload_paths = [payload_paths]

    context = []
    seen_fields = set()

    for path in payload_paths or []:
        if not path or path in seen_fields:
            continue

        seen_fields.add(path)
        value = get_nested_value(alert, path)

        if value is not None:
            context.append(
                {
                    "field": path,
                    "value": value,
                }
            )

    return context


# =========================
# NORMALIZATION HELPERS
# =========================
def normalize_alert_type(value: Any) -> str:
    """
    Normalize the operator-provided alert type.

    The translator does not infer alert_type. It only reads it through the
    field mapping received in the webhook payload.
    """
    if value is None:
        raise ValueError(
            "Missing alert_type. Check field_mapping.alert_type in configuration_data."
        )

    alert_type = str(value).strip().lower()

    if alert_type not in VALID_ALERT_TYPES:
        raise ValueError(
            f"Invalid alert_type '{value}'. Expected one of: {sorted(VALID_ALERT_TYPES)}"
        )

    return alert_type


def normalize_score_fields(raw_values: Dict[str, Any]) -> Dict[str, float]:
    """
    Normalize the three CVSS-derived maximum score fields from the webhook mapping.
    """
    if not isinstance(raw_values, dict):
        raise ValueError(
            "Missing or invalid score fields. Check max_cvss_base_score, max_impact_subscore and max_exploitability_subscore in field_mapping."
        )

    normalized = {}

    for field in REQUIRED_SCORE_FIELDS:
        if field not in raw_values:
            raise ValueError(f"Missing {field}")

        try:
            normalized[field] = float(raw_values[field])
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid {field}: expected numeric value, got {raw_values[field]!r}"
            ) from exc

    return normalized


def normalize_alert_input(raw_alert_data: Any) -> List[Dict[str, Any]]:
    """
    Accept:
      - single alert object
      - array of alerts
      - object containing alerts/value/records array
    """
    if isinstance(raw_alert_data, list):
        return [
            alert
            for alert in raw_alert_data
            if isinstance(alert, dict)
        ]

    if isinstance(raw_alert_data, dict):
        for key in ["alerts", "value", "records"]:
            if isinstance(raw_alert_data.get(key), list):
                return [
                    alert
                    for alert in raw_alert_data[key]
                    if isinstance(alert, dict)
                ]

        return [raw_alert_data]

    raise ValueError(
        "Unsupported alert format. Expected object, array, NDJSON, or object containing alerts/value/records array."
    )


def assert_processed_alert_schema(processed_alert: Dict[str, Any]) -> None:
    """
    Ensure every processed alert contains only the expected fields.
    """
    keys = set(processed_alert.keys())
    expected = set(NORMALIZED_ALERT_FIELDS)

    if keys != expected:
        extra = sorted(keys - expected)
        missing = sorted(expected - keys)

        raise ValueError(
            f"Invalid processed alert schema. Extra={extra}; missing={missing}"
        )


# =========================
# TRANSLATION LOGIC
# =========================
def translate_alert(
    alert: Dict[str, Any],
    config: Dict[str, Any],
    alert_id: int,
) -> Dict[str, Any]:
    """
    Translate one SIEM alert into the normalized alert schema.
    """
    time.sleep(5)  # Simula tiempo de espera para recibir datos por webhook
    mapping = config.get("field_mapping", {})

    name = get_nested_value(alert, mapping.get("name"))
    description = get_nested_value(alert, mapping.get("description"))
    ttps = extract_ttps(alert, mapping.get("ttps"))
    raw_alert_type = get_nested_value(alert, mapping.get("alert_type"))
    score_fields = {
        field: get_nested_value(alert, mapping.get(field))
        for field in REQUIRED_SCORE_FIELDS
    }
    normalized_scores = normalize_score_fields(score_fields)

    processed_alert = {
        "id": alert_id,
        "name": str(name).strip() if name else "Unnamed SIEM alert",
        "description": str(description).strip() if description else "No description provided by the SIEM alert.",
        "ttps": ttps,
        "alert_type": normalize_alert_type(raw_alert_type),
        "max_cvss_base_score": normalized_scores["max_cvss_base_score"],
        "max_impact_subscore": normalized_scores["max_impact_subscore"],
        "max_exploitability_subscore": normalized_scores["max_exploitability_subscore"],
        "payload_context": extract_payload_context(
            alert,
            mapping.get("payload_context"),
        ),
    }

    assert_processed_alert_schema(processed_alert)

    return processed_alert


def translate_alerts(
    raw_alert_data: Any,
    config: Dict[str, Any],
    existing_alerts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Translate alerts and append them to the in-memory alert collection.

    Output format:
      {
        "Normalized alerts": [
          {
            "id": 1,
            ...
          }
        ],
        "Number of normalized alerts": N
      }
    """
    input_alerts = normalize_alert_input(raw_alert_data)

    if existing_alerts is None:
        existing_alerts = []

    next_id = get_next_alert_id(existing_alerts)
    new_processed_alerts = []

    for raw_alert in input_alerts:
        processed_alert = translate_alert(
            alert=raw_alert,
            config=config,
            alert_id=next_id,
        )

        new_processed_alerts.append(processed_alert)
        next_id += 1

    all_alerts = existing_alerts + new_processed_alerts

    return {
        "Normalized alerts": all_alerts,
        "Number of normalized alerts": len(all_alerts),
    }


if __name__ == "__main__":
    raise SystemExit("translator.py now expects input data through the webhook.")
