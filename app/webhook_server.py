from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:
    from .engage_mapper import run_engage_mapper_from_collection
    from .translator import parse_alert_content, translate_alerts
except ImportError:
    from engage_mapper import run_engage_mapper_from_collection
    from translator import parse_alert_content, translate_alerts


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5668",
        "http://127.0.0.1:5668",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TRANSLATOR_STATE: Dict[str, Any] = {
    "alerts": [],
    "last_output": None,
}


def _filter_keys(data: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    return {key: data.get(key) for key in keys}


def _get_named_value(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return None


@app.post("/translator")
def run_translator(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    input_payload = payload.get("input") or payload
    named_inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}

    raw_alert_data = _get_named_value(
        named_inputs,
        "Raw SIEM alert",
        "input_data",
        "input_text",
    )
    raw_alert_text = None
    config = _get_named_value(
        named_inputs,
        "Translator configuration",
        "configuration_data",
    )

    if isinstance(input_payload, dict):
        raw_alert_data = (
            raw_alert_data
            if raw_alert_data is not None
            else _get_named_value(
                input_payload,
                "Raw SIEM alert",
                "input_data",
            )
        )
        raw_alert_text = input_payload.get("input_text")
        config = (
            config
            if config is not None
            else _get_named_value(
                input_payload,
                "Translator configuration",
                "configuration_data",
            )
        )

    if isinstance(raw_alert_data, str):
        raw_alert_data = parse_alert_content(raw_alert_data)
    elif raw_alert_data is None and raw_alert_text:
        raw_alert_data = parse_alert_content(raw_alert_text)

    if raw_alert_data is None:
        raise HTTPException(status_code=400, detail="Missing Raw SIEM alert")

    if not isinstance(config, dict):
        raise HTTPException(status_code=400, detail="Missing Translator configuration")

    try:
        output = translate_alerts(
            raw_alert_data=raw_alert_data,
            config=config,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    TRANSLATOR_STATE["alerts"] = output["Normalized alerts"]
    TRANSLATOR_STATE["last_output"] = output

    return {
        "hook": "translator",
        "success": True,
        "variables": _filter_keys(
            output,
            [
                "Normalized alerts",
                "Number of normalized alerts",
            ],
        ),
        "output": output,
    }


@app.post("/engage-mapper")
def run_engage_mapper(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    named_inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    alert_collection: Optional[Dict[str, Any]] = _get_named_value(
        named_inputs,
        "Normalized alerts",
    )

    if alert_collection is None:
        previous_output = payload.get("previous_output")
        if isinstance(previous_output, dict):
            alert_collection = (
                previous_output.get("Normalized alerts")
                or previous_output.get("alerts")
                or previous_output
            )
        else:
            alert_collection = previous_output

    if alert_collection is None:
        alert_collection = payload.get("translator_output") or TRANSLATOR_STATE.get("last_output")

    if not alert_collection:
        raise HTTPException(
            status_code=400,
            detail="Missing Normalized alerts. Run /translator first.",
        )

    try:
        output = run_engage_mapper_from_collection(alert_collection)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "hook": "engage_mapper",
        "success": True,
        "variables": _filter_keys(
            output,
            [
                "MITRE Engage recommendation",
            ],
        ),
        "output": output,
    }
