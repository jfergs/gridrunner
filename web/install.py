from datetime import datetime, timezone
import json

from fastapi import HTTPException, status

from config import INSTALL_MANIFEST_FILE, INSTALL_STATE_FILE, STATE_DIR


def load_install_items():
    with INSTALL_MANIFEST_FILE.open(encoding="utf-8") as manifest_file:
        items = json.load(manifest_file)

    seen = set()
    for item in items:
        item_id = item.get("id")
        if not item_id or item_id in seen:
            raise RuntimeError(f"Invalid install item id: {item_id}")
        seen.add(item_id)
        item.setdefault("default", False)

    return items


INSTALL_ITEMS = load_install_items()
INSTALL_ITEM_IDS = {item["id"] for item in INSTALL_ITEMS}
INSTALL_ITEMS_BY_ID = {item["id"]: item for item in INSTALL_ITEMS}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_install_state():
    try:
        with INSTALL_STATE_FILE.open(encoding="utf-8") as state_file:
            return json.load(state_file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {"error": "Install state file is invalid JSON."}


def save_install_state(state):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with INSTALL_STATE_FILE.open("w", encoding="utf-8") as state_file:
        json.dump(state, state_file, indent=2, sort_keys=True)
        state_file.write("\n")


def selected_install_items(form):
    selected = form.getlist("items")
    unknown = sorted(set(selected) - INSTALL_ITEM_IDS)
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown install item: {', '.join(unknown)}",
        )
    return selected


def parse_install_results(output):
    results = {}

    for line in output.splitlines():
        if not line.startswith("GRIDRUNNER_INSTALL_RESULT "):
            continue

        fields = {}
        for field in line.split()[1:]:
            key, _, value = field.partition("=")
            if key and value:
                fields[key] = value

        item_id = fields.get("item")
        status_value = fields.get("status")
        if item_id in INSTALL_ITEM_IDS and status_value in {"planned", "installed", "failed"}:
            results[item_id] = status_value

    return results


def install_statuses(state):
    legacy_selected = set(state.get("selected", []))
    legacy_skipped = set(state.get("skipped", []))
    state_items = state.get("items", {})
    statuses = {}

    for item in INSTALL_ITEMS:
        item_id = item["id"]
        item_state = state_items.get(item_id, {})
        status_value = item_state.get("status")

        if status_value in {"installed", "skipped", "pending", "failed"}:
            status_name = status_value
        elif item_id in legacy_selected and state.get("mode") == "apply":
            status_name = "installed"
        elif item_id in legacy_skipped:
            status_name = "skipped"
        else:
            status_name = "pending"

        statuses[item_id] = {
            "status": status_name,
            "last_run_at": item_state.get("last_run_at"),
            "label": item["label"],
        }

    return statuses


def update_install_state(mode, selected, results=None):
    existing = load_install_state()
    statuses = install_statuses(existing)
    selected_set = set(selected)
    results = results or {}
    timestamp = now_iso()

    for item_id in INSTALL_ITEM_IDS:
        result = results.get(item_id)
        if result == "installed":
            status_name = "installed"
        elif result == "failed":
            status_name = "failed"
        elif item_id in selected_set:
            if mode in {"dry-run", "skipped"}:
                status_name = statuses[item_id]["status"]
            else:
                status_name = "failed"
        elif mode in {"apply", "skipped"} and statuses[item_id]["status"] != "installed":
            status_name = "skipped"
        else:
            status_name = statuses[item_id]["status"]

        statuses[item_id] = {
            "status": status_name,
            "last_run_at": timestamp if item_id in selected_set or mode == "skipped" else statuses[item_id].get("last_run_at"),
            "label": INSTALL_ITEMS_BY_ID[item_id]["label"],
        }

    state = {
        "mode": mode,
        "selected": selected,
        "skipped": sorted(item_id for item_id, data in statuses.items() if data["status"] == "skipped"),
        "installed": sorted(item_id for item_id, data in statuses.items() if data["status"] == "installed"),
        "pending": sorted(item_id for item_id, data in statuses.items() if data["status"] == "pending"),
        "failed": sorted(item_id for item_id, data in statuses.items() if data["status"] == "failed"),
        "items": statuses,
        "last_run_at": timestamp,
    }
    save_install_state(state)
    return state
