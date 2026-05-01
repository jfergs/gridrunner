import os
import re
import secrets
import time

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from auth import require_auth
from commands import COMMANDS, run_cmd
from config import (
    ADSB_MAP_URL,
    DEVICE_HOSTNAME,
    EVENTS_LOG,
    EVENTS_STALE_SECONDS,
    OPERATOR_USER,
    SCAN_STATE_FILE,
    WEB_DIR,
    WEB_PASSWORD,
)
from install import (
    INSTALL_ITEMS,
    install_statuses,
    load_install_state,
    parse_component_health,
    parse_install_results,
    selected_install_items,
    update_install_state,
)

app = FastAPI()
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
POWER_ACTION_TOKEN = secrets.token_urlsafe(32)
SCAN_MODES = {"off", "continuous"}
SCAN_INTERVAL_MIN = 60
SCAN_INTERVAL_MAX = 1800
SCAN_INTERVAL_DEFAULT = 300


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


def adsb_map_url(request: Request):
    if ADSB_MAP_URL:
        return ADSB_MAP_URL

    hostname = request.url.hostname or f"{DEVICE_HOSTNAME}.local"
    if not re.fullmatch(r"[A-Za-z0-9.:-]+", hostname):
        hostname = f"{DEVICE_HOSTNAME}.local"
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    return f"http://{hostname}/tar1090/"


def event_freshness():
    try:
        stat_result = EVENTS_LOG.stat()
    except FileNotFoundError:
        return {
            "status": "missing",
            "message": "events log missing",
            "age_seconds": None,
        }
    except OSError:
        return {
            "status": "degraded",
            "message": "events log not readable",
            "age_seconds": None,
        }

    age_seconds = max(0, int(time.time() - stat_result.st_mtime))
    if age_seconds > EVENTS_STALE_SECONDS:
        return {
            "status": "stale",
            "message": f"events stale for {age_seconds}s",
            "age_seconds": age_seconds,
        }

    return {
        "status": "fresh",
        "message": f"events updated {age_seconds}s ago",
        "age_seconds": age_seconds,
    }


def recent_events():
    if not EVENTS_LOG.exists():
        return f"events log missing: {EVENTS_LOG}"
    if not EVENTS_LOG.is_file():
        return f"events log path is not a file: {EVENTS_LOG}"
    return run_cmd(["tail", "-n", "40", str(EVENTS_LOG)])


def clamp_scan_interval(value):
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = SCAN_INTERVAL_DEFAULT
    return min(SCAN_INTERVAL_MAX, max(SCAN_INTERVAL_MIN, interval))


def load_scan_controls():
    controls = {
        "bluetooth_mode": "off",
        "network_mode": "off",
        "interval_seconds": SCAN_INTERVAL_DEFAULT,
        "last_run": 0,
    }

    try:
        lines = SCAN_STATE_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return controls
    except OSError:
        controls["status"] = "unreadable"
        return controls

    for line in lines:
        key, _, value = line.partition("=")
        value = value.strip()
        if key == "GRIDRUNNER_SCAN_BLUETOOTH_MODE" and value in SCAN_MODES:
            controls["bluetooth_mode"] = value
        elif key == "GRIDRUNNER_SCAN_NETWORK_MODE" and value in SCAN_MODES:
            controls["network_mode"] = value
        elif key == "GRIDRUNNER_SCAN_INTERVAL_SECONDS":
            controls["interval_seconds"] = clamp_scan_interval(value)
        elif key == "GRIDRUNNER_SCAN_LAST_RUN":
            try:
                controls["last_run"] = max(0, int(value))
            except ValueError:
                controls["last_run"] = 0

    return controls


def save_scan_controls(controls):
    bluetooth_mode = controls.get("bluetooth_mode", "off")
    network_mode = controls.get("network_mode", "off")
    if bluetooth_mode not in SCAN_MODES:
        bluetooth_mode = "off"
    if network_mode not in SCAN_MODES:
        network_mode = "off"

    interval = clamp_scan_interval(controls.get("interval_seconds"))
    last_run = controls.get("last_run", 0)
    try:
        last_run = max(0, int(last_run))
    except (TypeError, ValueError):
        last_run = 0

    SCAN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCAN_STATE_FILE.write_text(
        "\n".join(
            [
                f"GRIDRUNNER_SCAN_BLUETOOTH_MODE={bluetooth_mode}",
                f"GRIDRUNNER_SCAN_NETWORK_MODE={network_mode}",
                f"GRIDRUNNER_SCAN_INTERVAL_SECONDS={interval}",
                f"GRIDRUNNER_SCAN_LAST_RUN={last_run}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_event_scan_once(target="all"):
    if target not in {"all", "bluetooth", "network"}:
        target = "all"

    env = os.environ.copy()
    env["GRIDRUNNER_SCAN_RUN_ONCE"] = "1"
    env["GRIDRUNNER_SCAN_ONCE_TARGET"] = target
    env["GRIDRUNNER_SCAN_STATE_FILE"] = str(SCAN_STATE_FILE)
    return run_cmd(COMMANDS["eventscan"], env=env)


def parse_keyed_status(output, prefix):
    for line in output.splitlines():
        if not line.startswith(prefix):
            continue

        fields = {}
        for field in line.split()[1:]:
            key, _, value = field.partition("=")
            if key:
                fields[key] = value.replace("_", " ")
        return fields

    return {}


def parse_prefixed_lines(output, prefixes):
    parsed = {}

    for line in output.splitlines():
        for prefix in prefixes:
            if line.startswith(prefix):
                parsed[prefix.strip()] = parse_keyed_status(line, prefix)
                break

    return parsed


def parse_service_health(output):
    services = {}

    for line in output.splitlines():
        if not line.startswith("GRIDRUNNER_SERVICE "):
            continue
        fields = parse_keyed_status(line, "GRIDRUNNER_SERVICE ")
        name = fields.get("name")
        if name:
            services[name] = fields

    return services


def severity_for_status(status_value):
    if status_value in {"present", "fresh", "active", "ok"}:
        return "ok"
    if status_value in {"missing", "failed", "critical"}:
        return "danger"
    return "warn"


def status_label(status_value):
    if severity_for_status(status_value) == "ok":
        return "OK"
    if severity_for_status(status_value) == "danger":
        return "FAIL"
    return "WARN"


def build_node_status(wifi_status, event_status, component_health):
    wifi_mode = wifi_status.get("mode", "unknown")
    wifi_health = wifi_status.get("status", "unknown")
    event_health = event_status.get("status", "unknown")
    adsb_health = component_health.get("adsb-tools", {}).get("status", "unknown")
    web_health = component_health.get("web-service", {}).get("status", "unknown")
    events_service_health = component_health.get("events-service", {}).get("status", "unknown")

    return [
        {"label": "NODE ONLINE", "severity": "ok"},
        {
            "label": f"WIFI {wifi_mode}".upper(),
            "severity": severity_for_status(wifi_health),
        },
        {
            "label": f"EVENTS {event_health}".upper(),
            "severity": severity_for_status(event_health),
        },
        {
            "label": f"EVENT TIMER {events_service_health}".upper(),
            "severity": severity_for_status(events_service_health),
        },
        {
            "label": f"ADS-B {adsb_health}".upper(),
            "severity": severity_for_status(adsb_health),
        },
        {
            "label": f"WEB {web_health}".upper(),
            "severity": severity_for_status(web_health),
        },
    ]


def service_check(name, service_name, services):
    service = services.get(service_name, {})
    status_value = service.get("status", "unknown")
    unit = service.get("unit", service_name)
    enabled = service.get("enabled", "unknown")

    return {
        "name": name,
        "status": status_value,
        "detail": f"{unit} {enabled}",
    }


def web_auth_status(auth_enabled):
    if auth_enabled:
        return {
            "status": "present",
            "detail": "password configured",
        }

    return {
        "status": "missing",
        "detail": "local or VPN only",
    }


def build_self_tests(wifi_status, event_status, component_health, health_output, services=None, auth_enabled=False):
    services = services or {}
    keyed = parse_prefixed_lines(
        health_output,
        [
            "GRIDRUNNER_DISK_HEALTH ",
            "GRIDRUNNER_ADSB_HEALTH ",
        ],
    )
    disk_status = keyed.get("GRIDRUNNER_DISK_HEALTH", {}).get("status", "unknown")
    adsb_status = keyed.get("GRIDRUNNER_ADSB_HEALTH", {}).get(
        "status",
        component_health.get("adsb-tools", {}).get("status", "unknown"),
    )

    checks = [
        {
            "name": "WEB AUTH",
            **web_auth_status(auth_enabled),
        },
        service_check("WEB SERVICE", "gridrunner-web", services),
        service_check("WI-FI TIMER", "gridrunner-wifi-timer", services),
        service_check("WI-FI SERVICE", "gridrunner-wifi", services),
        service_check("EVENT TIMER", "gridrunner-events-timer", services),
        service_check("READSB", "readsb", services),
        service_check("LIGHTTPD", "lighttpd", services),
        {
            "name": "EVENT FRESHNESS",
            "status": event_status.get("status", "unknown"),
            "detail": event_status.get("message", ""),
        },
        {
            "name": "ADS-B RTL",
            "status": adsb_status,
            "detail": component_health.get("adsb-tools", {}).get("detail", ""),
        },
        {
            "name": "DISK",
            "status": disk_status,
            "detail": keyed.get("GRIDRUNNER_DISK_HEALTH", {}).get("used_percent", "unknown"),
        },
    ]

    for check in checks:
        check["severity"] = severity_for_status(check["status"])
        check["label"] = status_label(check["status"])

    return checks


@app.get("/", response_class=HTMLResponse)
def index(request: Request, _user=Depends(require_auth)):
    status_output = run_cmd(COMMANDS["health"])
    events_output = recent_events()
    install_state = load_install_state()
    component_health = parse_component_health(run_cmd(COMMANDS["component_health"]))
    event_status = event_freshness()
    wifi_output = run_cmd(COMMANDS["wifi_status"])
    wifi_status = parse_keyed_status(wifi_output, "GRIDRUNNER_WIFI ")
    service_health = parse_service_health(run_cmd(COMMANDS["service_health"]))
    scan_controls = load_scan_controls()
    node_status = build_node_status(wifi_status, event_status, component_health)
    auth_enabled = bool(WEB_PASSWORD)
    self_tests = build_self_tests(
        wifi_status,
        event_status,
        component_health,
        status_output,
        service_health,
        auth_enabled,
    )

    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "status": status_output,
            "events": events_output,
            "event_status": event_status,
            "wifi_status": wifi_status,
            "wifi_output": wifi_output,
            "node_status": node_status,
            "self_tests": self_tests,
            "auth_enabled": auth_enabled,
            "operator_user": OPERATOR_USER,
            "adsb_map_url": adsb_map_url(request),
            "power_action_token": POWER_ACTION_TOKEN,
            "install_items": INSTALL_ITEMS,
            "install_state": install_state,
            "install_statuses": install_statuses(install_state),
            "component_health": component_health,
            "scan_controls": scan_controls,
        },
    )
    no_store(response)
    return response


@app.post("/scans", response_class=HTMLResponse)
def scan_action(
    request: Request,
    action: str = Form(...),
    scan_target: str = Form("all"),
    bluetooth_mode: str = Form("off"),
    network_mode: str = Form("off"),
    interval_seconds: int = Form(SCAN_INTERVAL_DEFAULT),
    _user=Depends(require_auth),
):
    controls = load_scan_controls()

    if action == "save":
        controls.update(
            {
                "bluetooth_mode": bluetooth_mode,
                "network_mode": network_mode,
                "interval_seconds": interval_seconds,
            }
        )
        save_scan_controls(controls)
        output = "Scan controls saved."
    elif action == "scan-now":
        output = run_event_scan_once(scan_target)
    else:
        output = f"Unknown scan action: {action}"

    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            "title": "GRIDRUNNER SCANS",
            "output": output,
        },
    )
    no_store(response)
    return response


@app.post("/run", response_class=HTMLResponse)
def run_action(
    request: Request,
    action: str = Form(...),
    _user=Depends(require_auth),
):
    cmd = COMMANDS.get(action)

    if not cmd:
        output = f"Unknown action: {action}"
    elif action in {"shutdown", "restart"}:
        output = "Power actions require the dedicated power form."
    else:
        output = run_cmd(cmd)

    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            "title": f"GRIDRUNNER: {action}",
            "output": output,
        },
    )
    no_store(response)
    return response


@app.post("/power", response_class=HTMLResponse)
def power_action(
    request: Request,
    action: str = Form(...),
    confirm_token: str = Form(""),
    _user=Depends(require_auth),
):
    if action not in {"shutdown", "restart"}:
        output = f"Unknown power action: {action}"
    elif not secrets.compare_digest(confirm_token, POWER_ACTION_TOKEN):
        output = "Power action rejected: invalid confirmation token."
    else:
        output = run_cmd(COMMANDS[action])

    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            "title": f"GRIDRUNNER POWER: {action}",
            "output": output,
        },
    )
    no_store(response)
    return response


@app.post("/install", response_class=HTMLResponse)
async def run_install(
    request: Request,
    mode: str = Form("dry-run"),
    _user=Depends(require_auth),
):
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
    update_install_state(mode, selected, parse_install_results(output))

    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            "title": f"GRIDRUNNER INSTALL: {mode}",
            "output": output,
        },
    )
    no_store(response)
    return response


@app.post("/install/skip")
async def skip_install(request: Request, _user=Depends(require_auth)):
    form = await request.form()
    selected = selected_install_items(form)
    update_install_state("skipped", selected)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
