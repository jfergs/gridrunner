from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import subprocess

app = FastAPI()
templates = Jinja2Templates(directory="templates")

COMMANDS = {
    "health": ["bash", "/home/ghost/gridrunner/scripts/ghost-health.sh"],
    "backup": ["bash", "/home/ghost/gridrunner/scripts/ghost-backup.sh"],
    "inventory": ["bash", "/home/ghost/gridrunner/scripts/radio-inventory.sh"],
    "hamcheck": ["bash", "/home/ghost/gridrunner/scripts/ham-check.sh"],
    "adsbmode": ["bash", "/home/ghost/gridrunner/scripts/radio-mode.sh", "adsb"],
    "sdrmode": ["bash", "/home/ghost/gridrunner/scripts/radio-mode.sh", "sdr"],
    "ghostevent": ["bash", "/home/ghost/ghost-events.sh"],
}

def run_cmd(cmd):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout + result.stderr
    except Exception as e:
        return f"ERROR: {e}"

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    status = run_cmd(["bash", "/home/ghost/gridrunner/scripts/ghost-health.sh"])
    events = run_cmd(["bash", "-lc", "tail -n 40 /home/ghost/ghost-events.log 2>/dev/null"])

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "status": status,
            "events": events,
        },
    )

@app.post("/run", response_class=HTMLResponse)
def run_action(action: str = Form(...)):
    cmd = COMMANDS.get(action)

    if not cmd:
        output = f"Unknown action: {action}"
    else:
        output = run_cmd(cmd)

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
      <h1>GRIDRUNNER: {action}</h1>
      <pre>{output}</pre>
      <a href="/">← Back</a>
    </body>
    </html>
    """)
