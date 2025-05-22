from fastapi import FastAPI, HTTPException
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
    if not acquire_lock(ip, container_id):
        raise HTTPException(status_code=400, detail="IP already has an active container")
    return JSONResponse(status_code=200, content={"container_id": container_id, "status": "locked"})

@app.post("/release")
async def release_container_lock(ip: str):
    """
    Release container lock for an IP address
    """
    if not release_lock(ip):
        raise HTTPException(status_code=400, detail="No active lock found for this IP")
    return JSONResponse(status_code=200, content={"status": "unlocked"})

@app.get("/check")
async def check_container_lock(ip: str):
    """
    Check if an IP has an active container lock
    """
    container_id = get_locked_container(ip)
    if not container_id:
        return JSONResponse(status_code=200, content={"status": "available"})
    return JSONResponse(status_code=200, content={"container_id": container_id, "status": "locked"})

@app.get("/active")
async def get_active():
    """
    Get all currently active (locked) containers
    """
    containers = get_active_containers()
    return JSONResponse(status_code=200, content={"active_containers": containers})

@app.get("/")
async def root():
    """
    Root endpoint for health check
    """
    return JSONResponse(status_code=200, content={"status": "Container Lock Service Active"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
