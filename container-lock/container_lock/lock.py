from redis import Redis
from container_lock.config import config
from fastapi import HTTPException
import logging
import docker

logger = logging.getLogger(__name__)

def get_redis_client(redis_url=None):
    return Redis.from_url(redis_url or config.REDIS_URL)

def is_managed_container(container_id: str) -> bool:
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        labels = container.labels
        return labels.get("sablier.group") == config.GROUP_LABEL
    except Exception as e:
        logger.error(f"Docker error during label check: {str(e)}")
        return False

def acquire_lock(ip: str, container_id: str, redis_client=None) -> bool:
    """
    Acquire an exclusive lock for a container by IP address
    Returns True if lock was successfully acquired
    Only one container per IP is allowed at a time
    """
    if not is_managed_container(container_id):
        raise HTTPException(status_code=403, detail="Container not managed by lock service")
    redis_client = redis_client or get_redis_client()
    try:
        # Check if IP already has a container
        existing_container = redis_client.get(f"lock:{ip}")
        if existing_container:
            existing_id = existing_container.decode() if isinstance(existing_container, bytes) else existing_container
            logger.warning(f"IP {ip} already has container {existing_id}")
            raise HTTPException(status_code=409, detail=f"IP already has active container: {existing_id}")

        # Check if the requested container is already locked by another IP
        for key in redis_client.scan_iter("lock:*"):
            other_ip = key.decode().split(":", 1)[1] if isinstance(key, bytes) else key.split(":", 1)[1]
            locked_container = redis_client.get(key)
            if locked_container:
                locked_id = locked_container.decode() if isinstance(locked_container, bytes) else locked_container
                if locked_id == container_id and other_ip != ip:
                    logger.warning(f"Container {container_id} already locked by IP {other_ip}")
                    raise HTTPException(status_code=409, detail=f"Container already in use by another user")

        # Set lock with TTL
        success = redis_client.setex(f"lock:{ip}", config.LOCK_TTL, container_id)
        if not success:
            logger.error(f"Failed to acquire lock for IP {ip} and container {container_id}")
            return False

        # Track active containers
        redis_client.sadd("active_containers", container_id)
        logger.info(f"IP {ip} successfully locked container {container_id}")
        return True
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Redis error during lock acquisition: {str(e)}")
        raise HTTPException(status_code=500, detail="Lock service unavailable")

def release_lock(ip: str, redis_client=None) -> bool:
    """
    Release container lock for a given IP address
    Returns True if lock existed and was successfully removed
    """
    redis_client = redis_client or get_redis_client()
    try:
        container_id = redis_client.get(f"lock:{ip}")
        if not container_id:
            return False
        container_id_str = container_id.decode() if isinstance(container_id, bytes) else container_id
        if not is_managed_container(container_id_str):
            raise HTTPException(status_code=403, detail="Container not managed by lock service")
        redis_client.delete(f"lock:{ip}")
        redis_client.srem("active_containers", container_id_str)
        logger.info(f"Released container {container_id_str} for IP {ip}")
        return True
    except Exception as e:
        logger.error(f"Redis error during lock release: {str(e)}")
        raise HTTPException(status_code=500, detail="Lock service unavailable")

def get_locked_container(ip: str, redis_client=None) -> str | None:
    """
    Get the container ID currently locked by an IP address
    Returns container ID string or None if no lock exists
    """
    redis_client = redis_client or get_redis_client()
    try:
        container_id = redis_client.get(f"lock:{ip}")
        if not container_id:
            return None
        container_id_str = container_id.decode() if isinstance(container_id, bytes) else container_id
        if not is_managed_container(container_id_str):
            return None
        return container_id_str
    except Exception as e:
        logger.error(f"Redis error during container lookup: {str(e)}")
        raise HTTPException(status_code=500, detail="Lock service unavailable")

def get_active_containers(redis_client=None) -> list[str]:
    redis_client = redis_client or get_redis_client()
    try:
        containers = redis_client.smembers("active_containers")
        return [c.decode() for c in containers]
    except Exception as e:
        logger.error(f"Redis error during active containers lookup: {str(e)}")
        raise HTTPException(status_code=500, detail="Lock service unavailable")
def get_user_active_container(ip: str, redis_client=None) -> dict | None:
    """
    Get the currently active container for a specific IP
    Returns container info or None if no active container
    """
    redis_client = redis_client or get_redis_client()
    try:
        container_id = redis_client.get(f"lock:{ip}")
        if not container_id:
            return None
        
        container_id_str = container_id.decode() if isinstance(container_id, bytes) else container_id
        
        # Get container details
        try:
            client = docker.from_env()
            container = client.containers.get(container_id_str)
            return {
                "container_id": container_id_str,
                "container_name": container.name,
                "container_status": container.status,
                "locked_by_ip": ip,
                "is_active": container.status == 'running'
            }
        except docker.errors.NotFound:
            # Container no longer exists, clean up the lock
            redis_client.delete(f"lock:{ip}")
            redis_client.srem("active_containers", container_id_str)
            return None
            
    except Exception as e:
        logger.error(f"Error getting user active container: {str(e)}")
        return None

def list_all_containers_with_locks(redis_client=None):
    """
    Returns a list of all managed containers with lock and status info.
    Each dict contains: id, name, status, locked_by_ip (or None)
    """
    redis_client = redis_client or get_redis_client()
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        result = []
        for container in containers:
            labels = container.labels
            if labels.get("sablier.group") != config.GROUP_LABEL:
                continue
            container_id = container.id
            name = container.name
            status = container.status
            # Find which IP (if any) has this container locked
            locked_by_ip = None
            for key in redis_client.scan_iter("lock:*"):
                ip = key.decode().split(":", 1)[1] if isinstance(key, bytes) else key.split(":", 1)[1]
                locked_id = redis_client.get(key)
                if locked_id:
                    locked_id = locked_id.decode() if isinstance(locked_id, bytes) else locked_id
                    if str(locked_id) == str(container_id):
                        locked_by_ip = ip
                        break
            result.append({
                "id": container_id,
                "name": name,
                "status": status,
                "locked_by_ip": locked_by_ip
            })
        return result
    except Exception as e:
        logger.error(f"Error listing containers with locks: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to list containers")

def list_all_containers() -> list[dict]:
    """
    Returns a list of all managed containers with name and status info.
    Each dict contains: id, name, status
    """
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        result = []
        for container in containers:
            # labels = container.labels
            # if labels.get("sablier.group") != config.GROUP_LABEL:
            #     continue # Skip containers not managed by this service
            container_id = container.id
            name = container.name
            status = container.status
            result.append({
                "id": container_id,
                "name": name,
                "status": status
            })
        return result
    except Exception as e:
        logger.error(f"Error listing containers: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to list containers")
        

def cleanup_exited_containers(redis_client=None) -> int:
    """
    Clean up locks for exited containers
    Returns number of locks cleaned up
    """
    redis_client = redis_client or get_redis_client()
    cleaned_count = 0
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        
        # Get all current locks
        for key in redis_client.scan_iter("lock:*"):
            ip = key.decode().split(":", 1)[1] if isinstance(key, bytes) else key.split(":", 1)[1]
            locked_container_id = redis_client.get(key)
            if locked_container_id:
                locked_container_id = locked_container_id.decode() if isinstance(locked_container_id, bytes) else locked_container_id
                
                # Check if the locked container exists and its status
                container_found = False
                for container in containers:
                    if container.id == locked_container_id:
                        container_found = True
                        # If container is exited, remove the lock
                        if container.status == 'exited':
                            redis_client.delete(key)
                            redis_client.srem("active_containers", locked_container_id)
                            logger.info(f"Cleaned up lock for exited container {locked_container_id} (IP: {ip})")
                            cleaned_count += 1
                        break
                
                # If container no longer exists, remove the lock
                if not container_found:
                    redis_client.delete(key)
                    redis_client.srem("active_containers", locked_container_id)
                    logger.info(f"Cleaned up lock for non-existent container {locked_container_id} (IP: {ip})")
                    cleaned_count += 1
                    
        return cleaned_count
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        return cleaned_count

def get_container_lock_status(container_id: str, redis_client=None) -> dict:
    """
    Get detailed lock status for a specific container
    Returns dict with lock info and container status
    """
    redis_client = redis_client or get_redis_client()
    try:
        client = docker.from_env()
        try:
            container = client.containers.get(container_id)
            container_status = container.status
            container_name = container.name
        except docker.errors.NotFound:
            return {
                "container_id": container_id,
                "container_name": "Unknown",
                "container_status": "not_found",
                "is_locked": False,
                "locked_by_ip": None,
                "is_clickable": False
            }
        
        # Check if container is locked
        locked_by_ip = None
        for key in redis_client.scan_iter("lock:*"):
            ip = key.decode().split(":", 1)[1] if isinstance(key, bytes) else key.split(":", 1)[1]
            locked_id = redis_client.get(key)
            if locked_id:
                locked_id = locked_id.decode() if isinstance(locked_id, bytes) else locked_id
                if str(locked_id) == str(container_id):
                    locked_by_ip = ip
                    break
        
        is_locked = locked_by_ip is not None
        # Container is clickable if it's not locked and running
        is_clickable = not is_locked and container_status == 'running'
        
        return {
            "container_id": container_id,
            "container_name": container_name,
            "container_status": container_status,
            "is_locked": is_locked,
            "locked_by_ip": locked_by_ip,
            "is_clickable": is_clickable
        }
    except Exception as e:
        logger.error(f"Error getting container lock status: {str(e)}")
        return {
            "container_id": container_id,
            "container_name": "Error",
            "container_status": "error",
            "is_locked": False,
            "locked_by_ip": None,
            "is_clickable": False
        }
