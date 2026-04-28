from pathlib import Path
import subprocess

from config import MAX_OUTPUT_CHARS, operator_script, project_script

COMMANDS = {
    "health": ["bash", project_script("system-health.sh")],
    "backup": ["bash", project_script("system-backup.sh")],
    "inventory": ["bash", project_script("radio-inventory.sh")],
    "hamcheck": ["bash", project_script("ham-check.sh")],
    "adsbmode": ["bash", project_script("radio-mode.sh"), "adsb"],
    "sdrmode": ["bash", project_script("radio-mode.sh"), "sdr"],
    "eventscan": ["bash", operator_script("operator-events.sh")],
    "install": ["bash", project_script("install-items.sh")],
    "component_health": ["bash", project_script("component-health.sh")],
    "shutdown": ["bash", project_script("power-control.sh"), "shutdown"],
    "restart": ["bash", project_script("power-control.sh"), "restart"],
}


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
