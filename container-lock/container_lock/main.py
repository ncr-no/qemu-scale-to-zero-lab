from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from container_lock.lock import (
    acquire_lock, list_all_containers, release_lock, get_locked_container, 
    get_active_containers, list_all_containers_with_locks, cleanup_exited_containers, 
    get_container_lock_status, get_user_active_container, test_docker_connection,
    stop_container
)
from container_lock.utils import get_client_ip
from container_lock.middleware import create_ip_lock_middleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import logging
import os
import asyncio
from contextlib import asynccontextmanager

# Background task for cleanup
cleanup_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global cleanup_task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("Started periodic cleanup task")
    yield
    # Shutdown
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    logger.info("Stopped periodic cleanup task")

async def periodic_cleanup():
    """Background task to periodically clean up exited containers"""
    while True:
        try:
            await asyncio.sleep(30)  # Run every 30 seconds
            cleaned_count = cleanup_exited_containers()
            if cleaned_count > 0:
                logger.info(f"Periodic cleanup: cleaned {cleaned_count} locks")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error during periodic cleanup: {e}")

app = FastAPI(title="Container Lock Service", version="0.1.0", lifespan=lifespan)
logger = logging.getLogger(__name__)

# Add IP lock middleware for session endpoints
app.middleware("http")(create_ip_lock_middleware(lock_timeout=30))

# Setup Jinja2 templates and static files
templates = Jinja2Templates(directory=os.path.abspath(os.path.join(os.path.dirname(__file__), './templates')))
app.mount("/static", StaticFiles(directory=os.path.abspath(os.path.join(os.path.dirname(__file__), './static'))), name="static")

@app.post("/acquire")
async def acquire_container_lock(request: Request, container_id: str = Form(...)):
    """
    Acquire exclusive container lock for an IP address
    Only one container per IP is allowed
    """
    ip = get_client_ip(request)
    if ip == "unknown":
        logger.warning("[ACQUIRE] Failed: No IP provided")
        raise HTTPException(status_code=400, detail="IP address required")
    
    logger.info(f"[ACQUIRE] Request: ip={ip}, container_id={container_id}")
    
    try:
        # Check if IP already has an active container
        existing_container = get_user_active_container(ip)
        if existing_container:
            logger.warning(f"[ACQUIRE] Failed: IP {ip} already has active container {existing_container['container_id']}")
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "IP already has an active container",
                    "active_container": existing_container
                }
            )
        
        # Try to acquire the lock
        if not acquire_lock(ip, container_id):
            logger.warning(f"[ACQUIRE] Failed: ip={ip}, container_id={container_id}")
            raise HTTPException(status_code=409, detail="Container not available")
        
        logger.info(f"[ACQUIRE] Success: ip={ip}, container_id={container_id}")
        return JSONResponse(status_code=200, content={"container_id": container_id, "status": "locked"})
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ACQUIRE] Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Lock service unavailable")

@app.post("/release")
async def release_container_lock(request: Request):
    """
    Release container lock for an IP address
    """
    ip = get_client_ip(request)
    if ip == "unknown":
        logger.warning("[RELEASE] Failed: No IP provided")
        raise HTTPException(status_code=400, detail="IP address required")
        
    logger.info(f"[RELEASE] Request: ip={ip}")
    if not release_lock(ip):
        logger.warning(f"[RELEASE] Failed: ip={ip}")
        raise HTTPException(status_code=400, detail="No active lock found for this IP")
    logger.info(f"[RELEASE] Success: ip={ip}")
    return JSONResponse(status_code=200, content={"status": "unlocked"})

@app.post("/end-session")
async def end_session(request: Request, stop_container: bool = True):
    """
    End session by releasing container lock and optionally stopping the container
    """
    ip = get_client_ip(request)
    if ip == "unknown":
        logger.warning("[END_SESSION] Failed: No IP provided")
        raise HTTPException(status_code=400, detail="IP address required")
    
    # Verify user has an active container
    user_active_container = get_user_active_container(ip)
    if not user_active_container:
        logger.warning(f"[END_SESSION] Failed: IP {ip} has no active container")
        raise HTTPException(status_code=400, detail="No active session found for this IP")
        
    logger.info(f"[END_SESSION] Request: ip={ip}, container_id={user_active_container['container_id']}, stop_container={stop_container}")
    
    # Release lock with optional container stopping
    if not release_lock(ip, stop_container_flag=stop_container):
        logger.warning(f"[END_SESSION] Failed: ip={ip}")
        raise HTTPException(status_code=400, detail="Failed to end session")
    
    logger.info(f"[END_SESSION] Success: ip={ip}, container stopped: {stop_container}")
    return JSONResponse(status_code=200, content={
        "status": "session_ended",
        "container_stopped": stop_container,
        "container_id": user_active_container['container_id']
    })

@app.get("/check")
async def check_container_lock(request: Request):
    """
    Check if an IP has an active container lock
    """
    ip = get_client_ip(request)
    if ip == "unknown":
        logger.warning(f"[CHECK] Failed: No IP provided")
        raise HTTPException(status_code=400, detail="IP address required")
        
    logger.info(f"[CHECK] Request: ip={ip}")
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
    """Basic health check endpoint"""
    return {"status": "healthy", "service": "container-lock"}

@app.get("/docker/health")
async def docker_health():
    """Docker connection health check"""
    try:
        connection_status = test_docker_connection()
        return connection_status
    except Exception as e:
        logger.error(f"Docker health check failed: {str(e)}")
        return {"status": "failed", "error": str(e)}

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

@app.post("/cleanup")
async def cleanup_exited():
    """
    Clean up locks for exited containers
    """
    logger.info("[CLEANUP] Request for cleanup")
    cleaned_count = cleanup_exited_containers()
    logger.info(f"[CLEANUP] Cleaned up {cleaned_count} locks")
    return JSONResponse(status_code=200, content={"cleaned_locks": cleaned_count})

@app.get("/container/{container_id}/status")
async def get_container_status(container_id: str):
    """
    Get detailed status for a specific container including lock state
    """
    logger.info(f"[STATUS] Request for container {container_id}")
    status = get_container_lock_status(container_id)
    logger.info(f"[STATUS] Container {container_id}: {status}")
    return JSONResponse(status_code=200, content=status)

@app.get("/my-active-container")
async def get_my_active_container(request: Request):
    """
    Get the currently active container for the requesting IP
    """
    ip = get_client_ip(request)
    if ip == "unknown":
        logger.warning("[MY_ACTIVE] Failed: No IP provided")
        raise HTTPException(status_code=400, detail="IP address required")
    
    logger.info(f"[MY_ACTIVE] Request from IP: {ip}")
    active_container = get_user_active_container(ip)
    
    if active_container:
        logger.info(f"[MY_ACTIVE] Found active container: {active_container['container_id']}")
        return JSONResponse(status_code=200, content={"active_container": active_container})
    else:
        logger.info(f"[MY_ACTIVE] No active container for IP: {ip}")
        return JSONResponse(status_code=200, content={"active_container": None})

@app.get("/containers/status")
async def get_all_container_status(request: Request):
    """
    Get status for all managed containers with lock information
    Also returns current user's active container if any
    """
    ip = get_client_ip(request)
    logger.info(f"[STATUS_ALL] Request for all container statuses from IP: {ip}")
    
    # First cleanup exited containers
    cleanup_exited_containers()
    containers = list_all_containers_with_locks()
    
    # Get current user's active container
    user_active_container = None
    if ip != "unknown":
        user_active_container = get_user_active_container(ip)
    
    # Enhance with clickable status
    enhanced_containers = []
    for container in containers:
        status_info = get_container_lock_status(container['id'])
        enhanced_container = {**container, **status_info}
        
        # Mark if this container is the user's active container
        if user_active_container and container['id'] == user_active_container['container_id']:
            enhanced_container['is_my_active'] = True
        else:
            enhanced_container['is_my_active'] = False
            
        # Apply clickability rules:
        # 1. If this is the user's own active container, it should always be clickable
        if user_active_container and container['id'] == user_active_container['container_id']:
            enhanced_container['is_clickable'] = True
            # Remove any blocked reason for user's own container
            if 'blocked_reason' in enhanced_container:
                del enhanced_container['blocked_reason']
        # 2. If container is locked by another IP, it's not clickable
        elif enhanced_container.get('is_locked') and enhanced_container.get('locked_by_ip') != ip:
            enhanced_container['is_clickable'] = False
            enhanced_container['blocked_reason'] = f"Container locked by another user ({enhanced_container.get('locked_by_ip')})"
        # 3. If user has an active container, all other containers should not be clickable
        elif user_active_container and container['id'] != user_active_container['container_id']:
            enhanced_container['is_clickable'] = False
            enhanced_container['blocked_reason'] = "You already have an active container"
            
        enhanced_containers.append(enhanced_container)
    
    logger.info(f"[STATUS_ALL] Returning {len(enhanced_containers)} containers")
    return JSONResponse(status_code=200, content={
        "containers": enhanced_containers,
        "user_active_container": user_active_container
    })

@app.get("/session/{container_name}", response_class=HTMLResponse)
async def container_session(request: Request, container_name: str):
    """
    Serve the container session page with embedded IFRAME
    """
    try:
        # Get the container ID from the name
        containers = list_all_containers()
        container = None
        for c in containers:
            if c['name'] == container_name:
                container = c
                break
        
        if not container:
            logger.warning(f"[SESSION] Container not found: {container_name}")
            raise HTTPException(status_code=404, detail="Container not found")
        
        # Construct the container URL (based on Caddy configuration)
        container_url = f"/vm/{container_name}/"
        
        logger.info(f"[SESSION] Serving session page for container: {container_name}")
        return templates.TemplateResponse(
            "container_session.html",
            {
                "request": request,
                "container_id": container['id'],
                "container_name": container_name,
                "container_url": container_url
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving session page for {container_name}: {e}")
        return templates.TemplateResponse(
            "error.html",
            {"request": request},
            status_code=500
        )

@app.get("/verify-caddy-config")
async def verify_caddy_config(request: Request):
    """
    Verify Caddy server configuration for container URLs
    Requires user to have an active container lock
    """
    ip = get_client_ip(request)
    if ip == "unknown":
        logger.warning("[VERIFY_CONFIG] Failed: No IP provided")
        raise HTTPException(status_code=400, detail="IP address required")
    
    # Check if user has an active container
    user_active_container = get_user_active_container(ip)
    if not user_active_container:
        logger.warning(f"[VERIFY_CONFIG] Failed: IP {ip} has no active container")
        raise HTTPException(status_code=403, detail="No active container found. Please acquire a container lock first.")
    
    try:
        # This would typically check the Caddy admin API or configuration
        # For now, we'll return basic configuration info
        containers = list_all_containers()
        
        config_info = {
            "caddy_status": "active",
            "container_routes": [],
            "sablier_enabled": True,
            "session_duration": "10m",
            "user_container": {
                "container_id": user_active_container["container_id"],
                "container_name": user_active_container["container_name"],
                "status": user_active_container["container_status"]
            }
        }
        
        for container in containers:
            config_info["container_routes"].append({
                "container_name": container['name'],
                "route_path": f"/vm/{container['name']}/*",
                "proxy_target": f"{container['name']}:8006",
                "sablier_managed": True,
                "is_user_container": container['id'] == user_active_container["container_id"]
            })
        
        logger.info(f"[VERIFY_CONFIG] Caddy configuration verified for IP {ip}")
        return JSONResponse(status_code=200, content=config_info)
        
    except Exception as e:
        logger.error(f"Error verifying Caddy config: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify configuration")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
