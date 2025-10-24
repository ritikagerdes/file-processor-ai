"""
Authentication API endpoints.
"""

import logging
from datetime import timedelta
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_database, verify_ip_address
from app.api.models import ClientCreate, ClientLogin, ClientResponse, TokenResponse
from app.core.database import db_manager
from app.core.security import security_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def register_client(
    client_data: ClientCreate,
    request: Request,
    db: Session = Depends(get_database)
) -> ClientResponse:
    """
    Register a new client.
    
    Args:
        client_data: Client registration data
        request: FastAPI request object
        db: Database session
        
    Returns:
        Created client data
        
    Raises:
        HTTPException: If registration fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        # Check if client already exists
        existing_client = db_manager.get_client_by_email(client_data.email)
        if existing_client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client with this email already exists"
            )
        
        # Hash password
        hashed_password = security_manager.hash_password(client_data.password)
        
        # Create client
        client_dict = {
            "id": security_manager.create_audit_hash(f"{client_data.email}_{client_data.name}")[:36],
            "name": client_data.name,
            "email": client_data.email,
            "hashed_password": hashed_password,
            "is_active": True
        }
        
        client = db_manager.create_client(client_dict)
        
        logger.info(f"New client registered: {client.email}")
        
        return ClientResponse(
            id=client.id,
            name=client.name,
            email=client.email,
            is_active=client.is_active,
            created_at=client.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Client registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login_client(
    login_data: ClientLogin,
    request: Request,
    db: Session = Depends(get_database)
) -> TokenResponse:
    """
    Authenticate client and return access token.
    
    Args:
        login_data: Client login data
        request: FastAPI request object
        db: Database session
        
    Returns:
        Access token and metadata
        
    Raises:
        HTTPException: If authentication fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        # Get client by email
        client = db_manager.get_client_by_email(login_data.email)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not security_manager.verify_password(login_data.password, client.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if client is active
        if not client.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Client account is inactive"
            )
        
        # Create access token
        token_data = {
            "client_id": client.id,
            "email": client.email,
            "name": client.name
        }
        
        access_token = security_manager.create_access_token(token_data)
        
        logger.info(f"Client logged in: {client.email}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=security_manager.access_token_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Client login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    current_client: Dict = Depends(security_manager.verify_token)
) -> TokenResponse:
    """
    Refresh access token.
    
    Args:
        request: FastAPI request object
        current_client: Current authenticated client data
        
    Returns:
        New access token and metadata
        
    Raises:
        HTTPException: If token refresh fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        # Create new access token
        token_data = {
            "client_id": current_client["client_id"],
            "email": current_client["email"],
            "name": current_client["name"]
        }
        
        access_token = security_manager.create_access_token(token_data)
        
        logger.info(f"Token refreshed for client: {current_client['email']}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=security_manager.access_token_expire_minutes * 60
        )
        
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout")
async def logout_client(
    request: Request,
    current_client: Dict = Depends(security_manager.verify_token)
) -> Dict[str, str]:
    """
    Logout client (client-side token invalidation).
    
    Args:
        request: FastAPI request object
        current_client: Current authenticated client data
        
    Returns:
        Logout confirmation message
    """
    # Verify IP address
    verify_ip_address(request)
    
    logger.info(f"Client logged out: {current_client['email']}")
    
    return {"message": "Successfully logged out"}