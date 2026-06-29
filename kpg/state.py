import json
import os
from datetime import datetime, timezone
from typing import Dict, Any


def load_state(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "positions": {},
            "portfolio": {
                "weekly_start_value": None,
                "daily_start_value": None,
                "high_water_mark": None,
            },
            "audit": [],
        }

    with open(path, "r") as f:
        return json.load(f)


def save_state(path: str, state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def audit(state: Dict[str, Any], event: Dict[str, Any]) -> None:
    event = dict(event)
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    state.setdefault("audit", []).append(event)
    state["audit"] = state["audit"][-500:]
