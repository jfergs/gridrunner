from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from auth import require_auth
from commands import COMMANDS, run_cmd
from config import ADSB_MAP_URL, EVENTS_LOG, OPERATOR_USER, WEB_DIR, WEB_PASSWORD
from install import (
    INSTALL_ITEMS,
    install_statuses,
    load_install_state,
    parse_install_results,
    selected_install_items,
    update_install_state,
)

app = FastAPI()
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def no_store(response: Response):
    response.headers["Cache-Control"] = "no-store"


@app.get("/", response_class=HTMLResponse)
def index(request: Request, _user=Depends(require_auth)):
    status_output = run_cmd(COMMANDS["health"])
    events_output = run_cmd(["tail", "-n", "40", str(EVENTS_LOG)])
    install_state = load_install_state()

    response = templates.TemplateResponse(
        request,
        "index.html",
        {
            "status": status_output,
            "events": events_output,
            "auth_enabled": bool(WEB_PASSWORD),
            "operator_user": OPERATOR_USER,
            "adsb_map_url": ADSB_MAP_URL,
            "install_items": INSTALL_ITEMS,
            "install_state": install_state,
            "install_statuses": install_statuses(install_state),
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
