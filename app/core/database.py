"""
Database models and operations for the secure file chatbot system.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text,
    create_engine, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.orm.session import Session

from app.config import settings

Base = declarative_base()


class Client(Base):
    """Client model for multi-tenant support."""
    
    __tablename__ = "clients"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    files = relationship("File", back_populates="client", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="client", cascade="all, delete-orphan")


class File(Base):
    """File model for storing file metadata."""
    
    __tablename__ = "files"
    
    id = Column(String(36), primary_key=True)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False)
    original_filename = Column(String(500), nullable=False)
    secure_filename = Column(String(500), nullable=False)
    file_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    s3_key = Column(String(1000), nullable=False)
    content_hash = Column(String(64), nullable=False)
    is_processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = relationship("Client", back_populates="files")
    chunks = relationship("FileChunk", back_populates="file", cascade="all, delete-orphan")


class FileChunk(Base):
    """File chunk model for storing processed file chunks with embeddings."""
    
    __tablename__ = "file_chunks"
    
    id = Column(String(36), primary_key=True)
    file_id = Column(String(36), ForeignKey("files.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_embedding = Column(LargeBinary, nullable=True)  # Encrypted embedding
    chunk_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    file = relationship("File", back_populates="chunks")


class Conversation(Base):
    """Conversation model for chat history."""
    
    __tablename__ = "conversations"
    
    id = Column(String(36), primary_key=True)
    client_id = Column(String(36), ForeignKey("clients.id"), nullable=False)
    title = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    client = relationship("Client", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Message model for individual chat messages."""
    
    __tablename__ = "messages"
    
    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    metadata = Column(Text, nullable=True)  # JSON string for additional data
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class DatabaseManager:
    """Database manager for handling database operations."""
    
    def __init__(self):
        """Initialize database manager with engine and session factory."""
        self.engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_recycle=300
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def create_tables(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self) -> Session:
        """Get database session."""
        return self.SessionLocal()
    
    def get_client_by_email(self, email: str) -> Optional[Client]:
        """Get client by email address."""
        session = self.get_session()
        try:
            return session.query(Client).filter(Client.email == email).first()
        finally:
            session.close()
    
    def get_client_by_id(self, client_id: str) -> Optional[Client]:
        """Get client by ID."""
        session = self.get_session()
        try:
            return session.query(Client).filter(Client.id == client_id).first()
        finally:
            session.close()
    
    def create_client(self, client_data: Dict[str, Any]) -> Client:
        """Create a new client."""
        session = self.get_session()
        try:
            client = Client(**client_data)
            session.add(client)
            session.commit()
            session.refresh(client)
            return client
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_files_by_client(self, client_id: str) -> List[File]:
        """Get all files for a client."""
        session = self.get_session()
        try:
            return session.query(File).filter(File.client_id == client_id).all()
        finally:
            session.close()
    
    def get_file_by_id(self, file_id: str) -> Optional[File]:
        """Get file by ID."""
        session = self.get_session()
        try:
            return session.query(File).filter(File.id == file_id).first()
        finally:
            session.close()
    
    def create_file(self, file_data: Dict[str, Any]) -> File:
        """Create a new file record."""
        session = self.get_session()
        try:
            file_record = File(**file_data)
            session.add(file_record)
            session.commit()
            session.refresh(file_record)
            return file_record
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def update_file_processing_status(self, file_id: str, is_processed: bool) -> None:
        """Update file processing status."""
        session = self.get_session()
        try:
            file_record = session.query(File).filter(File.id == file_id).first()
            if file_record:
                file_record.is_processed = is_processed
                session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def create_file_chunks(self, chunks_data: List[Dict[str, Any]]) -> List[FileChunk]:
        """Create file chunks."""
        session = self.get_session()
        try:
            chunks = [FileChunk(**chunk_data) for chunk_data in chunks_data]
            session.add_all(chunks)
            session.commit()
            return chunks
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_file_chunks(self, file_id: str) -> List[FileChunk]:
        """Get all chunks for a file."""
        session = self.get_session()
        try:
            return session.query(FileChunk).filter(FileChunk.file_id == file_id).all()
        finally:
            session.close()
    
    def create_conversation(self, conversation_data: Dict[str, Any]) -> Conversation:
        """Create a new conversation."""
        session = self.get_session()
        try:
            conversation = Conversation(**conversation_data)
            session.add(conversation)
            session.commit()
            session.refresh(conversation)
            return conversation
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_conversations_by_client(self, client_id: str) -> List[Conversation]:
        """Get all conversations for a client."""
        session = self.get_session()
        try:
            return session.query(Conversation).filter(
                Conversation.client_id == client_id
            ).order_by(Conversation.updated_at.desc()).all()
        finally:
            session.close()
    
    def create_message(self, message_data: Dict[str, Any]) -> Message:
        """Create a new message."""
        session = self.get_session()
        try:
            message = Message(**message_data)
            session.add(message)
            session.commit()
            session.refresh(message)
            return message
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_messages_by_conversation(self, conversation_id: str) -> List[Message]:
        """Get all messages for a conversation."""
        session = self.get_session()
        try:
            return session.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at.asc()).all()
        finally:
            session.close()


# Global database manager instance
db_manager = DatabaseManager()