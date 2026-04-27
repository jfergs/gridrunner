#!/bin/bash
set -eu

REPO_URL="${GRIDRUNNER_REPO_URL:-https://github.com/jfergs/gridrunner.git}"
INSTALL_DIR="${GRIDRUNNER_INSTALL_DIR:-$HOME/gridrunner}"
HOST="${GRIDRUNNER_WEB_HOST:-0.0.0.0}"
PORT="${GRIDRUNNER_WEB_PORT:-8088}"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required. Install git, then rerun this script."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required. Install python3 and python3-venv, then rerun this script."
  exit 1
fi

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating GRIDRUNNER in $INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --ff-only
elif [ -e "$INSTALL_DIR" ]; then
  echo "$INSTALL_DIR already exists and is not a git checkout."
  exit 1
else
  echo "Cloning GRIDRUNNER into $INSTALL_DIR"
  git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR/web"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

export GRIDRUNNER_HOME="$INSTALL_DIR"
export GRIDRUNNER_OPERATOR_USER="${GRIDRUNNER_OPERATOR_USER:-$(id -un)}"
export GRIDRUNNER_OPERATOR_HOME="${GRIDRUNNER_OPERATOR_HOME:-$HOME}"
export GRIDRUNNER_DEVICE_HOSTNAME="${GRIDRUNNER_DEVICE_HOSTNAME:-$(hostname -s)}"
export GRIDRUNNER_STATE_DIR="${GRIDRUNNER_STATE_DIR:-$INSTALL_DIR/state}"

cat <<EOF

GRIDRUNNER is ready.

Open:
  http://$GRIDRUNNER_DEVICE_HOSTNAME.local:$PORT

If mDNS is unavailable, use this device's IP address:
  http://<device-ip>:$PORT

EOF

exec .venv/bin/uvicorn app:app --host "$HOST" --port "$PORT"
