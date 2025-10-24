"""
File management API endpoints.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_client, get_database, verify_ip_address
from app.api.models import FileInfo, FileListResponse, FileUploadResponse
from app.core.database import db_manager
from app.core.file_processor import file_processor, FileProcessingError, UnsupportedFileTypeError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    request: Request,
    current_client: dict = Depends(get_current_client),
    db: Session = Depends(get_database)
) -> FileUploadResponse:
    """
    Upload and process a file.
    
    Args:
        file: Uploaded file
        request: FastAPI request object
        current_client: Current authenticated client
        db: Database session
        
    Returns:
        File upload response with processing results
        
    Raises:
        HTTPException: If upload or processing fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        # Validate file size
        file_data = await file.read()
        file_size_mb = len(file_data) / (1024 * 1024)
        
        if file_size_mb > 100:  # Max 100MB
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds maximum allowed size of 100MB"
            )
        
        # Process file
        result = file_processor.process_file(
            file_data=file_data,
            filename=file.filename,
            client_id=current_client["id"]
        )
        
        logger.info(f"File processed successfully: {file.filename} for client {current_client['id']}")
        
        return FileUploadResponse(
            file_id=result["file_id"],
            filename=result["filename"],
            file_type=result["file_type"],
            file_size=result["file_size"],
            chunks_created=result["chunks_created"],
            s3_url=result["s3_url"],
            status=result["status"],
            created_at=db_manager.get_file_by_id(result["file_id"]).created_at
        )
        
    except UnsupportedFileTypeError as e:
        logger.warning(f"Unsupported file type: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {str(e)}"
        )
    except FileProcessingError as e:
        logger.error(f"File processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File processing failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )


@router.get("/", response_model=FileListResponse)
async def list_files(
    request: Request,
    current_client: dict = Depends(get_current_client),
    db: Session = Depends(get_database)
) -> FileListResponse:
    """
    List all files for the current client.
    
    Args:
        request: FastAPI request object
        current_client: Current authenticated client
        db: Database session
        
    Returns:
        List of client files
        
    Raises:
        HTTPException: If listing fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        files = db_manager.get_files_by_client(current_client["id"])
        
        file_info_list = [
            FileInfo(
                id=file.id,
                original_filename=file.original_filename,
                file_type=file.file_type,
                file_size=file.file_size,
                is_processed=file.is_processed,
                created_at=file.created_at
            )
            for file in files
        ]
        
        return FileListResponse(
            files=file_info_list,
            total_count=len(file_info_list)
        )
        
    except Exception as e:
        logger.error(f"File listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list files"
        )


@router.get("/{file_id}", response_model=FileInfo)
async def get_file_info(
    file_id: str,
    request: Request,
    current_client: dict = Depends(get_current_client),
    db: Session = Depends(get_database)
) -> FileInfo:
    """
    Get information about a specific file.
    
    Args:
        file_id: File identifier
        request: FastAPI request object
        current_client: Current authenticated client
        db: Database session
        
    Returns:
        File information
        
    Raises:
        HTTPException: If file not found or access denied
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        file_record = db_manager.get_file_by_id(file_id)
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Verify client access
        if file_record.client_id != current_client["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return FileInfo(
            id=file_record.id,
            original_filename=file_record.original_filename,
            file_type=file_record.file_type,
            file_size=file_record.file_size,
            is_processed=file_record.is_processed,
            created_at=file_record.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File info retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file information"
        )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    request: Request,
    current_client: dict = Depends(get_current_client),
    db: Session = Depends(get_database)
) -> dict:
    """
    Delete a file and all its associated data.
    
    Args:
        file_id: File identifier
        request: FastAPI request object
        current_client: Current authenticated client
        db: Database session
        
    Returns:
        Deletion confirmation message
        
    Raises:
        HTTPException: If file not found or deletion fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        file_record = db_manager.get_file_by_id(file_id)
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Verify client access
        if file_record.client_id != current_client["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Delete from S3
        try:
            aws_manager.get_s3_client().delete_file(file_record.s3_key)
        except Exception as e:
            logger.warning(f"Failed to delete file from S3: {e}")
        
        # Delete from database (cascade will handle chunks)
        session = db_manager.get_session()
        try:
            session.delete(file_record)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
        
        logger.info(f"File deleted: {file_id} for client {current_client['id']}")
        
        return {"message": "File deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File deletion failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )