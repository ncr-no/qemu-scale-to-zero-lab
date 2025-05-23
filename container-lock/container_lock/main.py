from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from container_lock.lock import acquire_lock, list_all_containers, release_lock, get_locked_container, get_active_containers, list_all_containers_with_locks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import logging
import os

app = FastAPI(title="Container Lock Service", version="0.1.0")
logger = logging.getLogger(__name__)

# Setup Jinja2 templates and static files
templates = Jinja2Templates(directory=os.path.abspath(os.path.join(os.path.dirname(__file__), './templates')))
app.mount("/static", StaticFiles(directory=os.path.abspath(os.path.join(os.path.dirname(__file__), './static'))), name="static")

@app.post("/acquire")
async def acquire_container_lock(ip: str, container_id: str):
    """
    Acquire exclusive container lock for an IP address
    """
    logger.info(f"[ACQUIRE] Request: ip={ip}, container_id={container_id}")
    if not acquire_lock(ip, container_id):
        logger.warning(f"[ACQUIRE] Failed: ip={ip}, container_id={container_id}")
        raise HTTPException(status_code=400, detail="IP already has an active container")
    logger.info(f"[ACQUIRE] Success: ip={ip}, container_id={container_id}")
    return JSONResponse(status_code=200, content={"container_id": container_id, "status": "locked"})

@app.post("/release")
async def release_container_lock(ip: str):
    """
    Release container lock for an IP address
    """
    logger.info(f"[RELEASE] Request: ip={ip}")
    if not release_lock(ip):
        logger.warning(f"[RELEASE] Failed: ip={ip}")
        raise HTTPException(status_code=400, detail="No active lock found for this IP")
    logger.info(f"[RELEASE] Success: ip={ip}")
    return JSONResponse(status_code=200, content={"status": "unlocked"})

@app.get("/check")
async def check_container_lock(request: Request):
    """
    Check if an IP has an active container lock
    """
    logger.info(f"[CHECK] Request: header={request.headers.get('X-Real-IP')}")
    ip = request.headers.get("X-Real-IP")
    if not ip:
        logger.warning(f"[CHECK] Failed: No IP provided")
        raise HTTPException(status_code=400, detail="IP address required")
    container_id = get_locked_container(ip)
    if not container_id:
        logger.info(f"[CHECK] Available: ip={ip}")
        return JSONResponse(status_code=200, content={"status": "available"})
    logger.info(f"[CHECK] Locked: ip={ip}, container_id={container_id}")
    return JSONResponse(status_code=200, content={"container_id": container_id, "status": "locked"})

@app.get("/active")
async def get_active():
    """
    Get all currently active (locked) containers
    """
    logger.info("[ACTIVE] Request for all active containers")
    containers = get_active_containers()
    logger.info(f"[ACTIVE] Active containers: {containers}")
    return JSONResponse(status_code=200, content={"active_containers": containers})

@app.get("/health")
async def health():
    """
    Root endpoint for health check
    """
    logger.info("[ROOT] Health check")
    return JSONResponse(status_code=200, content={"status": "Container Lock Service Active"})

@app.get("/", response_class=HTMLResponse)
async def ui(request: Request):
    """
    Serve the container sessions UI
    """
    try:
        url = request.url
        containers = list_all_containers_with_locks()
        active_containers = [c for c in containers if c['status'] == 'running' and c['locked_by_ip']]
        available_containers = [c for c in containers if not c['locked_by_ip'] or c['status'] != 'running']
        available_containers = list_all_containers()
        return templates.TemplateResponse(
            "container_sessions.html",
            {
                "request": request,
                "active_containers": active_containers,
                "available_containers": available_containers,
                "url": url
            }
        )
    except Exception as e:
        logger.error(f"Error rendering UI: {e}")
        # Render an error page if fetching container data fails
        return templates.TemplateResponse(
            "error.html",
            {"request": request},
            status_code=500 # Internal Server Error
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
