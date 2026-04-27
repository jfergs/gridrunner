from html import escape
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import json
import os
import secrets
import subprocess

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

app = FastAPI()
security = HTTPBasic(auto_error=False)

WEB_DIR = Path(__file__).resolve().parent
PROJECT_DIR = Path(os.environ.get("GRIDRUNNER_HOME", WEB_DIR.parent))
OPERATOR_USER = os.environ.get("GRIDRUNNER_OPERATOR_USER", "operator")
OPERATOR_HOME = Path(
    os.environ.get(
        "GRIDRUNNER_OPERATOR_HOME",
        f"/home/{OPERATOR_USER}",
    )
)
DEVICE_HOSTNAME = os.environ.get("GRIDRUNNER_DEVICE_HOSTNAME", "device")
ADSB_MAP_URL = os.environ.get(
    "GRIDRUNNER_ADSB_MAP_URL",
    f"http://{DEVICE_HOSTNAME}.local/tar1090/",
)
EVENTS_LOG = Path(
    os.environ.get(
        "GRIDRUNNER_EVENTS_LOG",
        OPERATOR_HOME / "operator-events.log",
    )
)
WEB_USER = os.environ.get("GRIDRUNNER_WEB_USER", OPERATOR_USER)
WEB_PASSWORD = os.environ.get("GRIDRUNNER_WEB_PASSWORD", "")
MAX_OUTPUT_CHARS = int(os.environ.get("GRIDRUNNER_MAX_OUTPUT_CHARS", "20000"))
STATE_DIR = Path(os.environ.get("GRIDRUNNER_STATE_DIR", PROJECT_DIR / "state"))
INSTALL_STATE_FILE = STATE_DIR / "install.json"

templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))

INSTALL_ITEMS = [
    {
        "id": "base-tools",
        "label": "Base Tools",
        "description": "git, curl, jq, tmux, and htop.",
        "default": True,
    },
    {
        "id": "web-runtime",
        "label": "Web Runtime",
        "description": "Python runtime, venv support, and pip.",
        "default": True,
    },
    {
        "id": "operator-dirs",
        "label": "Operator Directories",
        "description": "Create data, logs, state, radio, and SDR directories.",
        "default": True,
    },
    {
        "id": "wifi-tools",
        "label": "Wi-Fi Fallback",
        "description": "NetworkManager tooling for known-network and hotspot fallback.",
        "default": True,
    },
    {
        "id": "radio-tools",
        "label": "SDR Tools",
        "description": "RTL-SDR and SoapySDR command-line utilities.",
        "default": False,
    },
    {
        "id": "adsb-tools",
        "label": "ADS-B Tools",
        "description": "readsb runtime package where available.",
        "default": False,
    },
    {
        "id": "ham-tools",
        "label": "Ham Tools",
        "description": "FLRig and basic packet radio utilities where available.",
        "default": False,
    },
]
INSTALL_ITEM_IDS = {item["id"] for item in INSTALL_ITEMS}
INSTALL_ITEMS_BY_ID = {item["id"]: item for item in INSTALL_ITEMS}


def project_script(name):
    return str(PROJECT_DIR / "scripts" / name)


def operator_script(name):
    return str(OPERATOR_HOME / name)


COMMANDS = {
    "health": ["bash", project_script("system-health.sh")],
    "backup": ["bash", project_script("system-backup.sh")],
    "inventory": ["bash", project_script("radio-inventory.sh")],
    "hamcheck": ["bash", project_script("ham-check.sh")],
    "adsbmode": ["bash", project_script("radio-mode.sh"), "adsb"],
    "sdrmode": ["bash", project_script("radio-mode.sh"), "sdr"],
    "eventscan": ["bash", operator_script("operator-events.sh")],
    "install": ["bash", project_script("install-items.sh")],
}


def require_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    if not WEB_PASSWORD:
        return None

    valid_user = credentials and secrets.compare_digest(credentials.username, WEB_USER)
    valid_password = credentials and secrets.compare_digest(credentials.password, WEB_PASSWORD)
    if valid_user and valid_password:
        return credentials.username

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Basic"},
    )


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


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


def install_statuses(state):
    legacy_selected = set(state.get("selected", []))
    legacy_skipped = set(state.get("skipped", []))
    state_items = state.get("items", {})
    statuses = {}

    for item in INSTALL_ITEMS:
        item_id = item["id"]
        item_state = state_items.get(item_id, {})
        status_value = item_state.get("status")

        if status_value in {"installed", "skipped", "pending"}:
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


def update_install_state(mode, selected):
    existing = load_install_state()
    statuses = install_statuses(existing)
    selected_set = set(selected)
    timestamp = now_iso()

    for item_id in INSTALL_ITEM_IDS:
        if item_id in selected_set:
            status_name = "installed" if mode == "apply" else statuses[item_id]["status"]
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
        "items": statuses,
        "last_run_at": timestamp,
    }
    save_install_state(state)
    return state


def run_cmd(cmd):
    script = Path(cmd[1])
    if cmd[:1] == ["bash"] and script.is_absolute() and not script.exists():
        return f"ERROR: missing script: {script}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n\n[output truncated]"
        return output
    except Exception as e:
        return f"ERROR: {e}"


@app.get("/", response_class=HTMLResponse)
def index(request: Request, response: Response, _user=Depends(require_auth)):
    status = run_cmd(COMMANDS["health"])
    events = run_cmd(["tail", "-n", "40", str(EVENTS_LOG)])
    install_state = load_install_state()
    no_store(response)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "status": status,
            "events": events,
            "auth_enabled": bool(WEB_PASSWORD),
            "operator_user": OPERATOR_USER,
            "adsb_map_url": ADSB_MAP_URL,
            "install_items": INSTALL_ITEMS,
            "install_state": install_state,
            "install_statuses": install_statuses(install_state),
        },
    )


@app.post("/run", response_class=HTMLResponse)
def run_action(response: Response, action: str = Form(...), _user=Depends(require_auth)):
    cmd = COMMANDS.get(action)
    no_store(response)

    if not cmd:
        output = f"Unknown action: {action}"
    else:
        output = run_cmd(cmd)

    safe_action = escape(action)
    safe_output = escape(output)

    return HTMLResponse(f"""
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        body {{ background:#0d1021; color:#f3e8ff; font-family: monospace; padding:20px; }}
        pre {{ white-space: pre-wrap; background:#16192b; padding:16px; border-radius:12px; }}
        a {{ color:#c084fc; }}
      </style>
    </head>
    <body>
      <h1>GRIDRUNNER: {safe_action}</h1>
      <pre>{safe_output}</pre>
      <a href="/">Back</a>
    </body>
    </html>
    """)


@app.post("/install", response_class=HTMLResponse)
async def run_install(
    request: Request,
    response: Response,
    mode: str = Form("dry-run"),
    _user=Depends(require_auth),
):
    no_store(response)
    form = await request.form()
    selected = selected_install_items(form)
    if mode not in {"dry-run", "apply"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid install mode.",
        )

    cmd = COMMANDS["install"][:]
    cmd.append("--apply" if mode == "apply" else "--dry-run")
    cmd.extend(selected)
    output = run_cmd(cmd)
    update_install_state(mode, selected)

    safe_mode = escape(mode)
    safe_output = escape(output)

    return HTMLResponse(f"""
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        body {{ background:#0d1021; color:#f3e8ff; font-family: monospace; padding:20px; }}
        pre {{ white-space: pre-wrap; background:#16192b; padding:16px; border-radius:12px; }}
        a {{ color:#c084fc; }}
      </style>
    </head>
    <body>
      <h1>GRIDRUNNER INSTALL: {safe_mode}</h1>
      <pre>{safe_output}</pre>
      <a href="/">Back</a>
    </body>
    </html>
    """)


@app.post("/install/skip")
async def skip_install(request: Request, _user=Depends(require_auth)):
    form = await request.form()
    selected = selected_install_items(form)
    update_install_state("skipped", selected)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
