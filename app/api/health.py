"""
Health check and monitoring API endpoints.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_database, verify_ip_address
from app.api.models import HealthResponse
from app.config import settings
from app.core.aws_client import aws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=HealthResponse)
async def health_check(
    request: Request,
    db: Session = Depends(get_database)
) -> HealthResponse:
    """
    Perform comprehensive health check of all services.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        Health status of all services
        
    Raises:
        HTTPException: If critical services are down
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        services = {}
        overall_status = "healthy"
        
        # Check database
        try:
            db.execute("SELECT 1")
            services["database"] = "healthy"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            services["database"] = "unhealthy"
            overall_status = "unhealthy"
        
        # Check S3
        try:
            aws_manager.get_s3_client().list_files(prefix="health-check/")
            services["s3"] = "healthy"
        except Exception as e:
            logger.error(f"S3 health check failed: {e}")
            services["s3"] = "unhealthy"
            overall_status = "unhealthy"
        
        # Check RDS
        try:
            aws_manager.get_rds_client().health_check()
            services["rds"] = "healthy"
        except Exception as e:
            logger.error(f"RDS health check failed: {e}")
            services["rds"] = "unhealthy"
            overall_status = "unhealthy"
        
        # Check OpenAI API (optional)
        try:
            import openai
            openai_client = openai.OpenAI(api_key=settings.openai_api_key)
            # Simple test call
            openai_client.models.list()
            services["openai"] = "healthy"
        except Exception as e:
            logger.warning(f"OpenAI API health check failed: {e}")
            services["openai"] = "unhealthy"
            # Don't mark overall as unhealthy for OpenAI issues
        
        return HealthResponse(
            status=overall_status,
            version=settings.app_version,
            timestamp=datetime.utcnow(),
            services=services
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )


@router.get("/ready")
async def readiness_check(
    request: Request,
    db: Session = Depends(get_database)
) -> dict:
    """
    Check if the service is ready to handle requests.
    
    Args:
        request: FastAPI request object
        db: Database session
        
    Returns:
        Readiness status
        
    Raises:
        HTTPException: If service is not ready
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        # Check critical services only
        db.execute("SELECT 1")
        aws_manager.get_s3_client().list_files(prefix="health-check/")
        aws_manager.get_rds_client().health_check()
        
        return {"status": "ready", "timestamp": datetime.utcnow()}
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )


@router.get("/live")
async def liveness_check(request: Request) -> dict:
    """
    Check if the service is alive (basic health check).
    
    Args:
        request: FastAPI request object
        
    Returns:
        Liveness status
    """
    # Verify IP address
    verify_ip_address(request)
    
    return {"status": "alive", "timestamp": datetime.utcnow()}