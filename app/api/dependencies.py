"""
API dependencies for authentication, authorization, and request validation.
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.database import db_manager
from app.core.security import security_manager, TokenError, IPWhitelistError

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()


def get_database() -> Session:
    """Get database session."""
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def verify_ip_address(request: Request) -> None:
    """
    Verify client IP address against whitelist.
    
    Args:
        request: FastAPI request object
        
    Raises:
        HTTPException: If IP address is not allowed
    """
    try:
        # Get client IP from request
        client_ip = request.client.host
        
        # Check for forwarded IP (in case of proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        # Verify IP address
        if not security_manager.verify_ip_address(client_ip):
            logger.warning(f"Unauthorized IP address attempt: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: IP address not authorized"
            )
    except IPWhitelistError as e:
        logger.error(f"IP verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


def get_current_client(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_database)
) -> dict:
    """
    Get current authenticated client from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        db: Database session
        
    Returns:
        Client data dictionary
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Verify token
        payload = security_manager.verify_token(credentials.credentials)
        client_id = payload.get("client_id")
        
        if not client_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing client_id"
            )
        
        # Get client from database
        client = db_manager.get_client_by_id(client_id)
        if not client or not client.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Client not found or inactive"
            )
        
        return {
            "id": client.id,
            "name": client.name,
            "email": client.email,
            "is_active": client.is_active
        }
        
    except TokenError as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


def verify_client_access(client_id: str, current_client: dict) -> None:
    """
    Verify that the current client has access to the requested resource.
    
    Args:
        client_id: Client ID from the request
        current_client: Current authenticated client data
        
    Raises:
        HTTPException: If access is denied
    """
    if current_client["id"] != client_id:
        logger.warning(
            f"Client {current_client['id']} attempted to access resource for client {client_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: insufficient permissions"
        )