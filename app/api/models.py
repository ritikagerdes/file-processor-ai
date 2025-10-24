"""
Pydantic models for API request/response validation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class ClientCreate(BaseModel):
    """Model for client creation."""
    name: str = Field(..., min_length=1, max_length=255, description="Client name")
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$', description="Client email address")
    password: str = Field(..., min_length=8, description="Client password")
    
    @validator('password')
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class ClientLogin(BaseModel):
    """Model for client login."""
    email: str = Field(..., description="Client email address")
    password: str = Field(..., description="Client password")


class ClientResponse(BaseModel):
    """Model for client response."""
    id: str
    name: str
    email: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Model for token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class FileUploadResponse(BaseModel):
    """Model for file upload response."""
    file_id: str
    filename: str
    file_type: str
    file_size: int
    chunks_created: int
    s3_url: str
    status: str
    created_at: datetime


class FileInfo(BaseModel):
    """Model for file information."""
    id: str
    original_filename: str
    file_type: str
    file_size: int
    is_processed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Model for file list response."""
    files: List[FileInfo]
    total_count: int


class ConversationCreate(BaseModel):
    """Model for conversation creation."""
    title: Optional[str] = Field(None, max_length=500, description="Conversation title")


class ConversationResponse(BaseModel):
    """Model for conversation response."""
    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    
    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    """Model for message creation."""
    content: str = Field(..., min_length=1, max_length=10000, description="Message content")
    conversation_id: Optional[str] = Field(None, description="Conversation ID (optional for new conversations)")


class MessageResponse(BaseModel):
    """Model for message response."""
    id: str
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    """Model for chat response."""
    message: MessageResponse
    conversation_id: str
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source documents used for response")


class SearchRequest(BaseModel):
    """Model for search request."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    max_results: int = Field(10, ge=1, le=50, description="Maximum number of results")
    file_types: Optional[List[str]] = Field(None, description="Filter by file types")


class SearchResult(BaseModel):
    """Model for search result."""
    file_id: str
    filename: str
    file_type: str
    chunk_text: str
    relevance_score: float
    chunk_index: int


class SearchResponse(BaseModel):
    """Model for search response."""
    query: str
    results: List[SearchResult]
    total_results: int


class ErrorResponse(BaseModel):
    """Model for error response."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Model for health check response."""
    status: str
    version: str
    timestamp: datetime
    services: Dict[str, str]


class ClientStatsResponse(BaseModel):
    """Model for client statistics response."""
    total_files: int
    total_conversations: int
    total_messages: int
    total_storage_bytes: int
    processed_files: int
    unprocessed_files: int