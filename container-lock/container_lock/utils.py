from fastapi import Request
import logging
import ipaddress

logger = logging.getLogger(__name__)

def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request using priority based on Caddy proxy guide:
    1. X-Forwarded-For (first IP in list) - Real client IP behind proxy chains
    2. X-Real-IP - Direct client IP from proxy
    3. request.client.host - Fallback for direct connections
    
    Args:
        request: FastAPI Request object
        
    Returns:
        str: Client IP address or "unknown" if extraction fails
    """
    
    # Priority 1: X-Forwarded-For header (handles proxy chains)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Split by comma and take the first (real client) IP
        ip_list = [ip.strip() for ip in forwarded_for.split(",")]
        if ip_list and ip_list[0]:
            client_ip = ip_list[0]
            if _is_valid_ip(client_ip):
                logger.debug(f"[IP_EXTRACT] X-Forwarded-For: {client_ip} (from chain: {forwarded_for})")
                return client_ip
    
    # Priority 2: X-Real-IP header (direct proxy)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        real_ip = real_ip.strip()
        if _is_valid_ip(real_ip):
            logger.debug(f"[IP_EXTRACT] X-Real-IP: {real_ip}")
            return real_ip
    
    # Priority 3: request.client.host (direct connection fallback)
    if request.client and request.client.host:
        direct_ip = request.client.host
        if _is_valid_ip(direct_ip):
            logger.debug(f"[IP_EXTRACT] Direct: {direct_ip}")
            return direct_ip
    
    # Log failure for debugging
    logger.warning(f"[IP_EXTRACT] Failed to extract valid IP. Headers: X-Forwarded-For={forwarded_for}, X-Real-IP={real_ip}, Direct={getattr(request.client, 'host', None) if request.client else None}")
    
    return "unknown"

def _is_valid_ip(ip: str) -> bool:
    """
    Validate if string is a valid IP address
    
    Args:
        ip: IP address string to validate
        
    Returns:
        bool: True if valid IP address
    """
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def get_real_ip_for_logs(request: Request) -> dict:
    """
    Get detailed IP information for logging/debugging purposes
    
    Args:
        request: FastAPI Request object
        
    Returns:
        dict: Dictionary with all IP extraction details
    """
    return {
        "extracted_ip": get_client_ip(request),
        "x_forwarded_for": request.headers.get("X-Forwarded-For"),
        "x_real_ip": request.headers.get("X-Real-IP"),
        "direct_ip": getattr(request.client, 'host', None) if request.client else None,
        "headers": dict(request.headers)
    } 