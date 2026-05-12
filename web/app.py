import json
import os
import re
import secrets
import time
from pathlib import Path
from urllib.parse import quote
from urllib.error import URLError
from urllib.request import urlopen

from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from auth import require_auth
from commands import COMMANDS, run_cmd
from config import (
    ADSB_MAP_URL,
    ADSB_AIRCRAFT_JSON,
    ADSB_ROUTE_API_URL,
    ADSB_ROUTE_CACHE_SECONDS,
    ADSB_ROUTE_LOOKUP_ENABLED,
    ADSB_ROUTE_LOOKUP_LIMIT,
    ADSB_ROUTE_LOOKUP_TIMEOUT,
    DEVICE_HOSTNAME,
    EVENTS_LOG,
    EVENTS_STALE_SECONDS,
    OPERATOR_HOME,
    OPERATOR_USER,
    PROJECT_DIR,
    SCAN_STATE_FILE,
    STORAGE_STATE_FILE,
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
FORM_ACTION_TOKEN = secrets.token_urlsafe(32)
POWER_ACTION_TOKEN = FORM_ACTION_TOKEN
SCAN_MODES = {"off", "continuous"}
SCAN_INTERVAL_MIN = 60
SCAN_INTERVAL_MAX = 1800
SCAN_INTERVAL_DEFAULT = 300
STORAGE_KEYS = {
    "GRIDRUNNER_STORAGE_MODE",
    "GRIDRUNNER_STORAGE_VOLUME_UUID",
    "GRIDRUNNER_STORAGE_MOUNT",
    "GRIDRUNNER_STORAGE_ROOT",
    "GRIDRUNNER_BACKUP_DIR",
    "GRIDRUNNER_EVENTS_LOG",
    "GRIDRUNNER_SDR_DIR",
    "GRIDRUNNER_RADIO_DIR",
    "GRIDRUNNER_ADSB_HISTORY_DIR",
    "GRIDRUNNER_MEDIA_DIR",
}
SCAN_PROFILES = {
    "low-impact": {
        "bluetooth_mode": "off",
        "network_device_mode": "off",
        "interval_seconds": 900,
        "label": "Low Impact",
    },
    "field": {
        "bluetooth_mode": "continuous",
        "network_device_mode": "continuous",
        "interval_seconds": 300,
        "label": "Field",
    },
}

ADSB_AIRCRAFT_CANDIDATES = [
    ADSB_AIRCRAFT_JSON,
    Path("/run/readsb/aircraft.json"),
    Path("/run/tar1090/aircraft.json"),
    ADSB_AIRCRAFT_JSON.parent / "data" / ADSB_AIRCRAFT_JSON.name,
]
ADSB_ROUTE_CACHE = {}


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


def valid_form_token(confirm_token):
    return secrets.compare_digest(confirm_token, FORM_ACTION_TOKEN)


def csrf_rejected_response(request, title):
    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            "title": title,
            "output": "Action rejected: invalid form token.",
        },
    )
    no_store(response)
    return response


def adsb_aircraft_file():
    for candidate in ADSB_AIRCRAFT_CANDIDATES:
        if candidate.exists():
            return candidate
    return ADSB_AIRCRAFT_JSON


def load_storage_config():
    config = {
        "GRIDRUNNER_STORAGE_MODE": "internal",
        "GRIDRUNNER_STORAGE_ROOT": "",
        "GRIDRUNNER_STORAGE_MOUNT": "",
        "GRIDRUNNER_STORAGE_VOLUME_UUID": "",
        "GRIDRUNNER_BACKUP_DIR": str(PROJECT_DIR / "data" / "backups"),
        "GRIDRUNNER_EVENTS_LOG": str(EVENTS_LOG),
        "GRIDRUNNER_SDR_DIR": str(PROJECT_DIR / "sdr"),
        "GRIDRUNNER_RADIO_DIR": str(PROJECT_DIR / "radio"),
        "GRIDRUNNER_ADSB_HISTORY_DIR": str(PROJECT_DIR / "data" / "adsb"),
        "GRIDRUNNER_MEDIA_DIR": str(PROJECT_DIR / "data" / "media"),
    }

    try:
        lines = STORAGE_STATE_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return config
    except OSError:
        config["GRIDRUNNER_STORAGE_MODE"] = "degraded"
        return config

    for line in lines:
        key, _, value = line.partition("=")
        if key in STORAGE_KEYS:
            config[key] = value.strip()

    return config


def internal_events_log():
    operator_log = OPERATOR_HOME / f"{OPERATOR_USER}-events.log"
    if operator_log.exists():
        return operator_log

    generic_log = OPERATOR_HOME / "operator-events.log"
    if generic_log.exists():
        return generic_log

    return operator_log


def active_events_log():
    config = load_storage_config()
    if (
        config.get("GRIDRUNNER_STORAGE_MODE") == "external"
        and config.get("GRIDRUNNER_STORAGE_ROOT")
        and Path(config["GRIDRUNNER_STORAGE_ROOT"]).is_dir()
        and os.access(config["GRIDRUNNER_STORAGE_ROOT"], os.W_OK)
        and config.get("GRIDRUNNER_EVENTS_LOG")
    ):
        return Path(config["GRIDRUNNER_EVENTS_LOG"])

    if config.get("GRIDRUNNER_STORAGE_MODE") == "internal":
        if EVENTS_LOG.exists():
            return EVENTS_LOG
        return internal_events_log()

    return EVENTS_LOG


def storage_summary(status_output=None):
    config = load_storage_config()
    mode = config.get("GRIDRUNNER_STORAGE_MODE", "internal") or "internal"
    root = config.get("GRIDRUNNER_STORAGE_ROOT", "")
    mount = config.get("GRIDRUNNER_STORAGE_MOUNT", "")
    uuid = config.get("GRIDRUNNER_STORAGE_VOLUME_UUID", "")
    status_value = "internal"
    warnings = []
    operator_message = "Internal storage paths are active."

    if mode == "external":
        if root and Path(root).is_dir() and os.access(root, os.W_OK):
            status_value = "external"
            operator_message = "External USB storage is active for operator data."
            if not uuid:
                warnings.append("external storage UUID unavailable")
        else:
            status_value = "degraded"
            warnings.append("external storage missing or not writable")
            operator_message = (
                "External storage is configured but unavailable; "
                "GRIDRUNNER is using internal backup and event-log paths."
            )

    return {
        "status": status_value,
        "mode": mode,
        "root": root or "internal",
        "mount": mount or "-",
        "uuid": uuid or "-",
        "warnings": warnings,
        "operator_message": operator_message,
        "backup_dir": config.get("GRIDRUNNER_BACKUP_DIR", str(PROJECT_DIR / "data" / "backups")),
        "events_log": str(active_events_log()),
        "sdr_dir": config.get("GRIDRUNNER_SDR_DIR", str(PROJECT_DIR / "sdr")),
        "radio_dir": config.get("GRIDRUNNER_RADIO_DIR", str(PROJECT_DIR / "radio")),
        "output": status_output if status_output is not None else run_cmd(COMMANDS["storage_status"]),
    }


def storage_volume_options(output):
    volumes = []
    for line in output.splitlines():
        if not line.startswith("GRIDRUNNER_STORAGE_VOLUME "):
            continue
        fields = parse_keyed_status(line, "GRIDRUNNER_STORAGE_VOLUME ", replace_underscores=False)
        mount = fields.get("mount", "")
        if mount and mount != "none" and fields.get("writable") == "yes" and fields.get("selectable") == "yes":
            volumes.append(fields)
    return volumes


def int_field(value, default=0):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def bytes_label(value):
    size = float(int_field(value))
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return "0 B"


def storage_volume_meters(output):
    meters = []
    for line in output.splitlines():
        if not line.startswith("GRIDRUNNER_STORAGE_VOLUME "):
            continue
        fields = parse_keyed_status(line, "GRIDRUNNER_STORAGE_VOLUME ", replace_underscores=False)
        mount = fields.get("mount", "")
        if not mount or mount == "none":
            continue

        used_percent = min(100, int_field(fields.get("used_percent")))
        used_bytes = int_field(fields.get("used_bytes"))
        avail_bytes = int_field(fields.get("avail_bytes"))
        size_bytes = int_field(fields.get("size_bytes"), used_bytes + avail_bytes)
        if size_bytes <= 0:
            continue
        if used_percent >= 95:
            severity = "danger"
        elif used_percent >= 85:
            severity = "warn"
        else:
            severity = "ok"
        meters.append(
            {
                "mount": mount,
                "source": fields.get("source", "unknown"),
                "fstype": fields.get("fstype", "unknown"),
                "severity": severity,
                "used_percent": used_percent,
                "free_percent": max(0, 100 - used_percent),
                "used_label": bytes_label(used_bytes),
                "free_label": bytes_label(avail_bytes),
                "size_label": bytes_label(size_bytes),
                "writable": fields.get("writable", "no"),
                "selectable": fields.get("selectable", "no"),
            }
        )
    return meters


def storage_mount_allowed(mount_path, volumes):
    return any(volume.get("mount") == mount_path and volume.get("writable") == "yes" for volume in volumes)


def short_aircraft_value(value, default="-"):
    if value in (None, ""):
        return default
    return str(value).strip() or default


def adsb_route_map_url(callsign):
    safe_callsign = re.sub(r"[^A-Za-z0-9]", "", callsign or "")
    if not safe_callsign:
        return ""
    return f"https://flightaware.com/live/flight/{quote(safe_callsign)}"


def parse_adsb_route_payload(payload):
    if not isinstance(payload, dict):
        return {}

    response = payload.get("response")
    if isinstance(response, dict):
        route = response.get("flightroute") or response.get("route") or response
    else:
        route = payload.get("flightroute") or payload.get("route") or payload

    if not isinstance(route, dict):
        return {}

    origin = route.get("origin") or route.get("from") or route.get("departure")
    destination = route.get("destination") or route.get("to") or route.get("arrival")
    airline = route.get("airline")

    if isinstance(origin, dict):
        origin = origin.get("icao_code") or origin.get("icao") or origin.get("iata_code") or origin.get("iata")
    if isinstance(destination, dict):
        destination = (
            destination.get("icao_code")
            or destination.get("icao")
            or destination.get("iata_code")
            or destination.get("iata")
        )
    if isinstance(airline, dict):
        airline = airline.get("name") or airline.get("icao") or airline.get("iata")

    origin = short_aircraft_value(origin, "")
    destination = short_aircraft_value(destination, "")
    if not origin and not destination:
        return {}

    route_label = f"{origin or '?'} -> {destination or '?'}"
    return {
        "origin": origin,
        "destination": destination,
        "airline": short_aircraft_value(airline, ""),
        "route": route_label,
    }


def adsb_route_lookup(callsign):
    clean_callsign = re.sub(r"[^A-Za-z0-9]", "", callsign or "")
    if not clean_callsign:
        return {}

    now = time.time()
    cached = ADSB_ROUTE_CACHE.get(clean_callsign)
    if cached and now - cached["at"] < ADSB_ROUTE_CACHE_SECONDS:
        return dict(cached["route"])

    lookup_url = ADSB_ROUTE_API_URL.format(callsign=quote(clean_callsign))
    try:
        with urlopen(lookup_url, timeout=ADSB_ROUTE_LOOKUP_TIMEOUT) as response:
            payload = json.loads(response.read(8192).decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return {}

    route = parse_adsb_route_payload(payload)
    if route:
        route["map_url"] = adsb_route_map_url(clean_callsign)
    ADSB_ROUTE_CACHE[clean_callsign] = {"at": now, "route": dict(route)}
    return route


def adsb_aircraft_summary(limit=5, now=None):
    aircraft_file = adsb_aircraft_file()
    summary = {
        "status": "missing",
        "message": "aircraft data missing",
        "updated_message": "aircraft file missing",
        "age_seconds": None,
        "count": 0,
        "aircraft": [],
        "path": str(aircraft_file),
    }

    try:
        aircraft_stat = aircraft_file.stat()
        data = json.loads(aircraft_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return summary
    except (OSError, json.JSONDecodeError):
        summary["status"] = "degraded"
        summary["message"] = "aircraft data unreadable"
        summary["updated_message"] = "aircraft file unreadable"
        return summary

    current_time = time.time() if now is None else now
    age_seconds = max(0, int(current_time - aircraft_stat.st_mtime))
    summary["age_seconds"] = age_seconds
    summary["updated_message"] = f"updated {age_seconds}s ago"

    aircraft = data.get("aircraft", [])
    if not isinstance(aircraft, list):
        summary["status"] = "degraded"
        summary["message"] = "aircraft data invalid"
        return summary

    seen_aircraft = [item for item in aircraft if isinstance(item, dict)]
    summary["status"] = "present"
    summary["count"] = len(seen_aircraft)
    summary["message"] = f"{len(seen_aircraft)} aircraft tracked"

    sortable = sorted(
        seen_aircraft,
        key=lambda item: item.get("seen", 999999)
        if isinstance(item.get("seen", 999999), (int, float))
        else 999999,
    )
    for index, item in enumerate(sortable[:limit]):
        seen = item.get("seen")
        if isinstance(seen, (int, float)):
            seen_text = f"{max(0, int(seen))}s"
        else:
            seen_text = "-"
        ident = short_aircraft_value(item.get("flight"), short_aircraft_value(item.get("hex")))
        route = {}
        if ADSB_ROUTE_LOOKUP_ENABLED and index < ADSB_ROUTE_LOOKUP_LIMIT:
            route = adsb_route_lookup(ident)
        summary["aircraft"].append(
            {
                "ident": ident,
                "altitude": short_aircraft_value(item.get("alt_baro", item.get("alt_geom"))),
                "speed": short_aircraft_value(item.get("gs")),
                "track": short_aircraft_value(item.get("track")),
                "seen": seen_text,
                "route": route.get("route", "-"),
                "airline": route.get("airline", ""),
                "route_map_url": route.get("map_url", adsb_route_map_url(ident)),
            }
        )

    return summary


def adsb_operator_guidance(summary, services=None):
    services = services or {}
    status_value = summary.get("status", "unknown")
    guidance = []

    if status_value in {"missing", "degraded"}:
        aircraft_path = summary.get("path", str(ADSB_AIRCRAFT_JSON))
        readsb = services.get("readsb", {}).get("status", "unknown")
        lighttpd = services.get("lighttpd", {}).get("status", "unknown")
        guidance.extend(
            [
                f"Aircraft file: {aircraft_path}",
                f"readsb.service: {readsb}",
                f"lighttpd.service: {lighttpd}",
                "Run bash scripts/adsb-health.sh on the device.",
            ]
        )
    elif summary.get("age_seconds") is not None and summary["age_seconds"] > 30:
        guidance.append("Aircraft data is aging; check readsb if the count stops changing.")

    return guidance


def event_freshness():
    events_log = active_events_log()
    try:
        stat_result = events_log.stat()
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


def event_dashboard_status(event_status, scan_controls):
    dashboard_status = dict(event_status)
    dashboard_status["log_path"] = str(active_events_log())

    if (
        scan_controls.get("bluetooth_mode") == "off"
        and scan_controls.get("network_device_mode") == "off"
        and event_status.get("status") in {"missing", "stale"}
    ):
        dashboard_status["status"] = "idle"
        dashboard_status["message"] = "idle: Bluetooth and Network scans are disabled"
        dashboard_status["detail"] = "Enable scanning or run a one-shot scan to write new events."
    else:
        dashboard_status["detail"] = f"writing to {dashboard_status['log_path']}"

    return dashboard_status


def recent_events():
    events_log = active_events_log()
    if not events_log.exists():
        return f"events log missing: {events_log}"
    if not events_log.is_file():
        return f"events log path is not a file: {events_log}"
    return run_cmd(["tail", "-n", "40", str(events_log)])


def clamp_scan_interval(value):
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = SCAN_INTERVAL_DEFAULT
    return min(SCAN_INTERVAL_MAX, max(SCAN_INTERVAL_MIN, interval))


def load_scan_controls():
    controls = {
        "bluetooth_mode": "off",
        "network_device_mode": "off",
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
        elif key == "GRIDRUNNER_SCAN_NETWORK_DEVICE_MODE" and value in SCAN_MODES:
            controls["network_device_mode"] = value
        elif key == "GRIDRUNNER_SCAN_NETWORK_MODE" and value in SCAN_MODES:
            controls["network_device_mode"] = value
        elif key == "GRIDRUNNER_SCAN_INTERVAL_SECONDS":
            controls["interval_seconds"] = clamp_scan_interval(value)
        elif key == "GRIDRUNNER_SCAN_LAST_RUN":
            try:
                controls["last_run"] = max(0, int(value))
            except ValueError:
                controls["last_run"] = 0

    return controls


def scan_profile_for(controls):
    for profile_id, profile in SCAN_PROFILES.items():
        if (
            controls.get("bluetooth_mode") == profile["bluetooth_mode"]
            and controls.get("network_device_mode") == profile["network_device_mode"]
            and clamp_scan_interval(controls.get("interval_seconds")) == profile["interval_seconds"]
        ):
            return {
                "id": profile_id,
                "label": profile["label"],
            }

    return {
        "id": "custom",
        "label": "Custom",
    }


def describe_scan_controls(controls, now=None):
    now = int(time.time() if now is None else now)
    described = dict(controls)
    active = []

    if described.get("bluetooth_mode") == "continuous":
        active.append("Bluetooth")
    if described.get("network_device_mode") == "continuous":
        active.append("Network Devices")

    described["active_scanners"] = ", ".join(active) if active else "none"
    described["state_label"] = "armed" if active else "off"
    described["profile"] = scan_profile_for(described)

    try:
        last_run = int(described.get("last_run", 0))
    except (TypeError, ValueError):
        last_run = 0

    if last_run > 0:
        age_seconds = max(0, now - last_run)
        described["last_run_message"] = f"last scan {age_seconds}s ago"
    else:
        described["last_run_message"] = "last scan never"

    described["mode_summary"] = (
        f"Bluetooth {described.get('bluetooth_mode', 'off')}; "
        f"Network Devices {described.get('network_device_mode', 'off')}; "
        f"interval {described.get('interval_seconds', SCAN_INTERVAL_DEFAULT)}s"
    )

    return described


def save_scan_controls(controls):
    bluetooth_mode = controls.get("bluetooth_mode", "off")
    network_device_mode = controls.get("network_device_mode", controls.get("network_mode", "off"))
    if bluetooth_mode not in SCAN_MODES:
        bluetooth_mode = "off"
    if network_device_mode not in SCAN_MODES:
        network_device_mode = "off"

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
                f"GRIDRUNNER_SCAN_NETWORK_DEVICE_MODE={network_device_mode}",
                f"GRIDRUNNER_SCAN_NETWORK_MODE={network_device_mode}",
                f"GRIDRUNNER_SCAN_INTERVAL_SECONDS={interval}",
                f"GRIDRUNNER_SCAN_LAST_RUN={last_run}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def scan_controls_for_profile(profile_id, current_controls=None):
    controls = dict(current_controls or load_scan_controls())
    profile = SCAN_PROFILES.get(profile_id)
    if not profile:
        return controls

    controls.update(
        {
            "bluetooth_mode": profile["bluetooth_mode"],
            "network_device_mode": profile["network_device_mode"],
            "interval_seconds": profile["interval_seconds"],
        }
    )
    return controls


def toggle_scan_controls(current_controls=None):
    controls = dict(current_controls or load_scan_controls())
    described = describe_scan_controls(controls)

    if described["state_label"] == "armed":
        controls.update(
            {
                "bluetooth_mode": "off",
                "network_device_mode": "off",
                "interval_seconds": SCAN_INTERVAL_DEFAULT,
            }
        )
    else:
        controls = scan_controls_for_profile("field", controls)

    return controls


def run_event_scan_once(target="all"):
    if target not in {"all", "bluetooth", "network"}:
        target = "all"

    env = os.environ.copy()
    env["GRIDRUNNER_SCAN_RUN_ONCE"] = "1"
    env["GRIDRUNNER_SCAN_ONCE_TARGET"] = target
    env["GRIDRUNNER_SCAN_STATE_FILE"] = str(SCAN_STATE_FILE)
    return run_cmd(COMMANDS["eventscan"], env=env)


def scan_action_payload(action, scan_target="all", current_controls=None):
    controls = dict(current_controls or load_scan_controls())
    output = ""
    notice = ""

    if action.startswith("profile:"):
        profile_id = action.partition(":")[2]
        controls = scan_controls_for_profile(profile_id, controls)
        save_scan_controls(controls)
        described = describe_scan_controls(controls)
        profile = described["profile"]
        notice = (
            f"Scan profile applied: {profile['label']}. "
            f"Continuous scans armed: {described['active_scanners']}."
        )
    elif action == "toggle":
        controls = toggle_scan_controls(controls)
        save_scan_controls(controls)
        described = describe_scan_controls(controls)
        if described["state_label"] == "armed":
            notice = f"Scanning enabled: {described['active_scanners']}."
        else:
            notice = "Scanning disabled."
    elif action == "scan-now":
        output = run_event_scan_once(scan_target)
        controls["last_run"] = int(time.time())
        save_scan_controls(controls)
        label = "Bluetooth" if scan_target == "bluetooth" else "Wi-Fi Device"
        notice = f"{label} scan finished."
    else:
        notice = f"Unknown scan action: {action}"

    described = describe_scan_controls(controls)
    return {
        "notice": notice,
        "output": output,
        "controls": described,
    }


def parse_keyed_status(output, prefix, replace_underscores=True):
    for line in output.splitlines():
        if not line.startswith(prefix):
            continue

        fields = {}
        for field in line.split()[1:]:
            key, _, value = field.partition("=")
            if key:
                fields[key] = value.replace("_", " ") if replace_underscores else value
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
    if status_value in {"present", "fresh", "active", "ok", "idle"}:
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
    wifi_output = run_cmd(COMMANDS["wifi_status"])
    wifi_status = parse_keyed_status(wifi_output, "GRIDRUNNER_WIFI ")
    service_health = parse_service_health(run_cmd(COMMANDS["service_health"]))
    scan_controls = describe_scan_controls(load_scan_controls())
    event_status = event_dashboard_status(event_freshness(), scan_controls)
    adsb_summary = adsb_aircraft_summary()
    storage_status_output = run_cmd(COMMANDS["storage_status"])
    storage_list_output = run_cmd(COMMANDS["storage_list"])
    storage = storage_summary(storage_status_output)
    storage_volumes = storage_volume_options(storage_list_output)
    storage_meters = storage_volume_meters(storage_list_output)
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
            "adsb_summary": adsb_summary,
            "adsb_guidance": adsb_operator_guidance(adsb_summary, service_health),
            "form_action_token": FORM_ACTION_TOKEN,
            "power_action_token": POWER_ACTION_TOKEN,
            "install_items": INSTALL_ITEMS,
            "install_state": install_state,
            "install_statuses": install_statuses(install_state),
            "component_health": component_health,
            "scan_controls": scan_controls,
            "scan_notice": request.query_params.get("scan_notice", ""),
            "storage": storage,
            "storage_volumes": storage_volumes,
            "storage_meters": storage_meters,
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
    network_device_mode: str = Form(""),
    network_mode: str = Form(""),
    interval_seconds: int = Form(SCAN_INTERVAL_DEFAULT),
    confirm_token: str = Form(""),
    _user=Depends(require_auth),
):
    if not valid_form_token(confirm_token):
        return csrf_rejected_response(request, "GRIDRUNNER SCANS")

    controls = load_scan_controls()

    if action == "save":
        network_device_mode = network_device_mode or network_mode
        controls.update(
            {
                "bluetooth_mode": bluetooth_mode,
                "network_device_mode": network_device_mode,
                "interval_seconds": interval_seconds,
            }
        )
        save_scan_controls(controls)
        output = "Scan controls saved."
    elif action.startswith("profile:"):
        payload = scan_action_payload(action, current_controls=controls)
        notice = f"{payload['notice']} Use scan-now buttons for immediate output."
        response = RedirectResponse(f"/?scan_notice={quote(notice)}#scans", status_code=status.HTTP_303_SEE_OTHER)
        no_store(response)
        return response
    elif action == "toggle":
        payload = scan_action_payload(action, current_controls=controls)
        response = RedirectResponse(f"/?scan_notice={quote(payload['notice'])}#scans", status_code=status.HTTP_303_SEE_OTHER)
        no_store(response)
        return response
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


@app.post("/scans/api")
def scan_api_action(
    action: str = Form(...),
    scan_target: str = Form("all"),
    confirm_token: str = Form(""),
    _user=Depends(require_auth),
):
    if not valid_form_token(confirm_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid form token")

    payload = scan_action_payload(action, scan_target=scan_target)
    response = JSONResponse(payload)
    no_store(response)
    return response


@app.post("/storage", response_class=HTMLResponse)
def storage_action(
    request: Request,
    action: str = Form(...),
    mount_path: str = Form(""),
    confirm_token: str = Form(""),
    _user=Depends(require_auth),
):
    if not valid_form_token(confirm_token):
        return csrf_rejected_response(request, "GRIDRUNNER STORAGE")

    if action == "enable":
        if not mount_path:
            output = "No USB storage volume selected."
        elif not storage_mount_allowed(mount_path, storage_volume_options(run_cmd(COMMANDS["storage_list"]))):
            output = f"USB storage volume is not available or writable: {mount_path}"
        else:
            output = run_cmd(COMMANDS["storage_enable"] + [mount_path])
    elif action == "disable":
        output = run_cmd(COMMANDS["storage_disable"])
    elif action == "status":
        output = run_cmd(COMMANDS["storage_status"])
    else:
        output = f"Unknown storage action: {action}"

    response = templates.TemplateResponse(
        request,
        "result.html",
        {
            "title": "GRIDRUNNER STORAGE",
            "output": output,
        },
    )
    no_store(response)
    return response


@app.post("/run", response_class=HTMLResponse)
def run_action(
    request: Request,
    action: str = Form(...),
    confirm_token: str = Form(""),
    _user=Depends(require_auth),
):
    if not valid_form_token(confirm_token):
        return csrf_rejected_response(request, f"GRIDRUNNER: {action}")

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
    elif not valid_form_token(confirm_token):
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
    confirm_token: str = Form(""),
    _user=Depends(require_auth),
):
    if not valid_form_token(confirm_token):
        return csrf_rejected_response(request, f"GRIDRUNNER INSTALL: {mode}")

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
async def skip_install(
    request: Request,
    confirm_token: str = Form(""),
    _user=Depends(require_auth),
):
    if not valid_form_token(confirm_token):
        return csrf_rejected_response(request, "GRIDRUNNER INSTALL: skipped")

    form = await request.form()
    selected = selected_install_items(form)
    update_install_state("skipped", selected)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
