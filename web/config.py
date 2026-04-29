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
EVENTS_LOG = Path(
    os.environ.get(
        "GRIDRUNNER_EVENTS_LOG",
        OPERATOR_HOME / "operator-events.log",
    )
)
WEB_USER = os.environ.get("GRIDRUNNER_WEB_USER", OPERATOR_USER)
WEB_PASSWORD = os.environ.get("GRIDRUNNER_WEB_PASSWORD", "")
MAX_OUTPUT_CHARS = int(os.environ.get("GRIDRUNNER_MAX_OUTPUT_CHARS", "20000"))
EVENTS_STALE_SECONDS = int(os.environ.get("GRIDRUNNER_EVENTS_STALE_SECONDS", "86400"))
STATE_DIR = Path(os.environ.get("GRIDRUNNER_STATE_DIR", PROJECT_DIR / "state"))
INSTALL_STATE_FILE = STATE_DIR / "install.json"
INSTALL_MANIFEST_FILE = PROJECT_DIR / "install-items.json"


def project_script(name):
    return str(PROJECT_DIR / "scripts" / name)


def operator_script(name):
    return str(OPERATOR_HOME / name)
