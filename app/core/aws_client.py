"""
AWS service clients for S3, RDS, and other AWS services.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import settings

logger = logging.getLogger(__name__)


class AWSServiceError(Exception):
    """AWS service operation error."""
    pass


class S3Client:
    """S3 client for file storage operations."""
    
    def __init__(self):
        """Initialize S3 client with credentials."""
        try:
            self.client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
            self.bucket_name = settings.aws_s3_bucket
        except NoCredentialsError as e:
            raise AWSServiceError("AWS credentials not found") from e
    
    def upload_file(self, file_data: bytes, key: str, metadata: Optional[Dict[str, str]] = None) -> str:
        """
        Upload file to S3.
        
        Args:
            file_data: File data as bytes
            key: S3 object key
            metadata: Optional metadata for the object
            
        Returns:
            S3 object URL
            
        Raises:
            AWSServiceError: If upload fails
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_data,
                **extra_args
            )
            
            return f"s3://{self.bucket_name}/{key}"
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise AWSServiceError(f"S3 upload failed: {str(e)}") from e
    
    def download_file(self, key: str) -> bytes:
        """
        Download file from S3.
        
        Args:
            key: S3 object key
            
        Returns:
            File data as bytes
            
        Raises:
            AWSServiceError: If download fails
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise AWSServiceError(f"S3 download failed: {str(e)}") from e
    
    def delete_file(self, key: str) -> bool:
        """
        Delete file from S3.
        
        Args:
            key: S3 object key
            
        Returns:
            True if deletion successful
            
        Raises:
            AWSServiceError: If deletion fails
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            raise AWSServiceError(f"S3 deletion failed: {str(e)}") from e
    
    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        List files in S3 bucket with optional prefix.
        
        Args:
            prefix: Optional prefix to filter files
            
        Returns:
            List of file metadata dictionaries
            
        Raises:
            AWSServiceError: If listing fails
        """
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag']
                    })
            
            return files
        except ClientError as e:
            logger.error(f"Failed to list files in S3: {e}")
            raise AWSServiceError(f"S3 listing failed: {str(e)}") from e


class RDSClient:
    """RDS client for database operations."""
    
    def __init__(self):
        """Initialize RDS client with connection."""
        try:
            self.engine = create_engine(
                f"postgresql://{settings.aws_rds_username}:{settings.aws_rds_password}@"
                f"{settings.aws_rds_endpoint}:5432/{settings.aws_rds_database}",
                pool_pre_ping=True,
                pool_recycle=300
            )
        except Exception as e:
            raise AWSServiceError(f"Failed to connect to RDS: {str(e)}") from e
    
    def get_engine(self) -> Engine:
        """Get SQLAlchemy engine."""
        return self.engine
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Query results as list of dictionaries
            
        Raises:
            AWSServiceError: If query execution fails
        """
        try:
            with self.engine.connect() as connection:
                result = connection.execute(text(query), params or {})
                return [dict(row._mapping) for row in result]
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            raise AWSServiceError(f"Query execution failed: {str(e)}") from e
    
    def health_check(self) -> bool:
        """
        Check database connection health.
        
        Returns:
            True if connection is healthy
            
        Raises:
            AWSServiceError: If health check fails
        """
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            raise AWSServiceError(f"Database health check failed: {str(e)}") from e


class AWSManager:
    """Centralized AWS service manager."""
    
    def __init__(self):
        """Initialize AWS manager with all service clients."""
        self.s3 = S3Client()
        self.rds = RDSClient()
    
    def get_s3_client(self) -> S3Client:
        """Get S3 client."""
        return self.s3
    
    def get_rds_client(self) -> RDSClient:
        """Get RDS client."""
        return self.rds


# Global AWS manager instance
aws_manager = AWSManager()