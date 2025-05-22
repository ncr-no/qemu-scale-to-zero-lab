from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from container_lock.lock import acquire_lock, release_lock, get_locked_container, get_active_containers
import logging

app = FastAPI(title="Container Lock Service", version="0.1.0")
logger = logging.getLogger(__name__)

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

@app.get("/")
async def root():
    """
    Root endpoint for health check
    """
    logger.info("[ROOT] Health check")
    return JSONResponse(status_code=200, content={"status": "Container Lock Service Active"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
