from pathlib import Path
import os

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
ADSB_MAP_URL = os.environ.get("GRIDRUNNER_ADSB_MAP_URL", "")
ADSB_AIRCRAFT_JSON = Path(
    os.environ.get(
        "GRIDRUNNER_ADSB_AIRCRAFT_JSON",
        "/run/readsb/aircraft.json",
    )
)
ADSB_ROUTE_LOOKUP_ENABLED = os.environ.get("GRIDRUNNER_ADSB_ROUTE_LOOKUP_ENABLED", "1") == "1"
ADSB_ROUTE_API_URL = os.environ.get("GRIDRUNNER_ADSB_ROUTE_API_URL", "https://api.adsbdb.com/v0/callsign/{callsign}")
ADSB_ROUTE_LOOKUP_LIMIT = int(os.environ.get("GRIDRUNNER_ADSB_ROUTE_LOOKUP_LIMIT", "3"))
ADSB_ROUTE_LOOKUP_TIMEOUT = float(os.environ.get("GRIDRUNNER_ADSB_ROUTE_LOOKUP_TIMEOUT", "0.8"))
ADSB_ROUTE_CACHE_SECONDS = int(os.environ.get("GRIDRUNNER_ADSB_ROUTE_CACHE_SECONDS", "900"))


def resolve_events_log():
    configured = os.environ.get("GRIDRUNNER_EVENTS_LOG")
    if configured:
        return Path(configured)

    operator_log = OPERATOR_HOME / f"{OPERATOR_USER}-events.log"
    if operator_log.exists():
        return operator_log

    generic_log = OPERATOR_HOME / "operator-events.log"
    if generic_log.exists():
        return generic_log

    return operator_log


EVENTS_LOG = resolve_events_log()
WEB_USER = os.environ.get("GRIDRUNNER_WEB_USER", OPERATOR_USER)
WEB_PASSWORD = os.environ.get("GRIDRUNNER_WEB_PASSWORD", "")
MAX_OUTPUT_CHARS = int(os.environ.get("GRIDRUNNER_MAX_OUTPUT_CHARS", "20000"))
EVENTS_STALE_SECONDS = int(os.environ.get("GRIDRUNNER_EVENTS_STALE_SECONDS", "900"))
STATE_DIR = Path(os.environ.get("GRIDRUNNER_STATE_DIR", PROJECT_DIR / "state"))
INSTALL_STATE_FILE = STATE_DIR / "install.json"
INSTALL_MANIFEST_FILE = PROJECT_DIR / "install-items.json"
SCAN_STATE_FILE = STATE_DIR / "scan-controls.env"
STORAGE_STATE_FILE = STATE_DIR / "storage.env"
EDGE_NODE_STATE_DIR = Path(os.environ.get("GRIDRUNNER_EDGE_NODE_STATE_DIR", STATE_DIR / "edge-nodes"))
EDGE_NODE_STALE_SECONDS = int(os.environ.get("GRIDRUNNER_EDGE_NODE_STALE_SECONDS", "900"))


def project_script(name):
    return str(PROJECT_DIR / "scripts" / name)


def operator_script(name):
    return str(OPERATOR_HOME / name)
