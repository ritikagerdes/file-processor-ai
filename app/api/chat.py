"""
Chat and search API endpoints.
"""

import json
import logging
from typing import List, Optional

import openai
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_client, get_database, verify_ip_address
from app.api.models import (
    ChatResponse, ConversationCreate, ConversationResponse, MessageCreate,
    MessageResponse, SearchRequest, SearchResponse, SearchResult
)
from app.config import settings
from app.core.database import db_manager
from app.core.file_processor import file_processor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ConversationCreate,
    request: Request,
    current_client: dict = Depends(get_current_client),
    db: Session = Depends(get_database)
) -> ConversationResponse:
    """
    Create a new conversation.
    
    Args:
        conversation_data: Conversation creation data
        request: FastAPI request object
        current_client: Current authenticated client
        db: Database session
        
    Returns:
        Created conversation data
        
    Raises:
        HTTPException: If conversation creation fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        conversation_dict = {
            "id": security_manager.create_audit_hash(f"{current_client['id']}_{conversation_data.title or 'untitled'}")[:36],
            "client_id": current_client["id"],
            "title": conversation_data.title
        }
        
        conversation = db_manager.create_conversation(conversation_dict)
        
        logger.info(f"Conversation created: {conversation.id} for client {current_client['id']}")
        
        return ConversationResponse(
            id=conversation.id,
            title=conversation.title,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            message_count=0
        )
        
    except Exception as e:
        logger.error(f"Conversation creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation"
        )


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    request: Request,
    current_client: dict = Depends(get_current_client),
    db: Session = Depends(get_database)
) -> List[ConversationResponse]:
    """
    List all conversations for the current client.
    
    Args:
        request: FastAPI request object
        current_client: Current authenticated client
        db: Database session
        
    Returns:
        List of conversations
        
    Raises:
        HTTPException: If listing fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        conversations = db_manager.get_conversations_by_client(current_client["id"])
        
        conversation_list = []
        for conv in conversations:
            message_count = len(db_manager.get_messages_by_conversation(conv.id))
            conversation_list.append(ConversationResponse(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=message_count
            ))
        
        return conversation_list
        
    except Exception as e:
        logger.error(f"Conversation listing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list conversations"
        )


@router.post("/search", response_model=SearchResponse)
async def search_files(
    search_request: SearchRequest,
    request: Request,
    current_client: dict = Depends(get_current_client),
    db: Session = Depends(get_database)
) -> SearchResponse:
    """
    Search through client's files for relevant content.
    
    Args:
        search_request: Search parameters
        request: FastAPI request object
        current_client: Current authenticated client
        db: Database session
        
    Returns:
        Search results with relevance scores
        
    Raises:
        HTTPException: If search fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        # Get all files for the client
        files = db_manager.get_files_by_client(current_client["id"])
        
        # Filter by file types if specified
        if search_request.file_types:
            files = [f for f in files if f.file_type in search_request.file_types]
        
        # Search through file chunks
        search_results = []
        
        for file in files:
            if not file.is_processed:
                continue
                
            try:
                chunks = file_processor.get_file_chunks_for_search(file.id)
                
                for chunk in chunks:
                    # Calculate relevance score (simple text matching for now)
                    query_lower = search_request.query.lower()
                    chunk_lower = chunk["chunk_text"].lower()
                    
                    # Simple relevance scoring
                    relevance_score = 0
                    if query_lower in chunk_lower:
                        relevance_score += 1
                    
                    # Count word matches
                    query_words = query_lower.split()
                    chunk_words = chunk_lower.split()
                    word_matches = sum(1 for word in query_words if word in chunk_words)
                    relevance_score += word_matches * 0.1
                    
                    if relevance_score > 0:
                        search_results.append(SearchResult(
                            file_id=file.id,
                            filename=file.original_filename,
                            file_type=file.file_type,
                            chunk_text=chunk["chunk_text"],
                            relevance_score=min(relevance_score, 1.0),
                            chunk_index=chunk["chunk_index"]
                        ))
                        
            except Exception as e:
                logger.warning(f"Failed to search file {file.id}: {e}")
                continue
        
        # Sort by relevance score
        search_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Limit results
        search_results = search_results[:search_request.max_results]
        
        return SearchResponse(
            query=search_request.query,
            results=search_results,
            total_results=len(search_results)
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )


@router.post("/message", response_model=ChatResponse)
async def send_message(
    message_data: MessageCreate,
    request: Request,
    current_client: dict = Depends(get_current_client),
    db: Session = Depends(get_database)
) -> ChatResponse:
    """
    Send a message and get AI response with context from files.
    
    Args:
        message_data: Message data
        request: FastAPI request object
        current_client: Current authenticated client
        db: Database session
        
    Returns:
        AI response with sources
        
    Raises:
        HTTPException: If message processing fails
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        # Get or create conversation
        conversation_id = message_data.conversation_id
        if not conversation_id:
            # Create new conversation
            conversation = db_manager.create_conversation({
                "id": security_manager.create_audit_hash(f"{current_client['id']}_new_conversation")[:36],
                "client_id": current_client["id"],
                "title": message_data.content[:50] + "..." if len(message_data.content) > 50 else message_data.content
            })
            conversation_id = conversation.id
        
        # Save user message
        user_message = db_manager.create_message({
            "id": security_manager.create_audit_hash(f"{conversation_id}_user_{message_data.content}")[:36],
            "conversation_id": conversation_id,
            "role": "user",
            "content": message_data.content
        })
        
        # Search for relevant context
        search_request = SearchRequest(
            query=message_data.content,
            max_results=5
        )
        
        search_response = await search_files(
            search_request=search_request,
            request=request,
            current_client=current_client,
            db=db
        )
        
        # Prepare context for AI
        context = ""
        sources = []
        
        for result in search_response.results:
            context += f"From {result.filename} (chunk {result.chunk_index}):\n{result.chunk_text}\n\n"
            sources.append({
                "filename": result.filename,
                "file_type": result.file_type,
                "chunk_index": result.chunk_index,
                "relevance_score": result.relevance_score
            })
        
        # Generate AI response
        try:
            openai_client = openai.OpenAI(api_key=settings.openai_api_key)
            
            system_prompt = f"""You are a helpful assistant that answers questions based on the provided context from the user's files. 
            
            Context from files:
            {context}
            
            Instructions:
            - Answer the user's question based on the provided context
            - If the context doesn't contain enough information, say so
            - Be helpful and accurate
            - Cite the source files when relevant
            - Keep responses concise but informative
            """
            
            response = openai_client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message_data.content}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            ai_response = "I apologize, but I'm unable to process your request at the moment. Please try again later."
            sources = []
        
        # Save AI response
        ai_message = db_manager.create_message({
            "id": security_manager.create_audit_hash(f"{conversation_id}_ai_{ai_response}")[:36],
            "conversation_id": conversation_id,
            "role": "assistant",
            "content": ai_response,
            "metadata": json.dumps({"sources": sources})
        })
        
        logger.info(f"Message processed for conversation {conversation_id}")
        
        return ChatResponse(
            message=MessageResponse(
                id=ai_message.id,
                role=ai_message.role,
                content=ai_message.content,
                metadata=json.loads(ai_message.metadata) if ai_message.metadata else None,
                created_at=ai_message.created_at
            ),
            conversation_id=conversation_id,
            sources=sources
        )
        
    except Exception as e:
        logger.error(f"Message processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process message"
        )


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    request: Request,
    current_client: dict = Depends(get_current_client),
    db: Session = Depends(get_database)
) -> List[MessageResponse]:
    """
    Get all messages for a conversation.
    
    Args:
        conversation_id: Conversation identifier
        request: FastAPI request object
        current_client: Current authenticated client
        db: Database session
        
    Returns:
        List of messages
        
    Raises:
        HTTPException: If conversation not found or access denied
    """
    # Verify IP address
    verify_ip_address(request)
    
    try:
        # Verify conversation belongs to client
        conversations = db_manager.get_conversations_by_client(current_client["id"])
        conversation_ids = [conv.id for conv in conversations]
        
        if conversation_id not in conversation_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
        
        messages = db_manager.get_messages_by_conversation(conversation_id)
        
        message_list = [
            MessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                metadata=json.loads(msg.metadata) if msg.metadata else None,
                created_at=msg.created_at
            )
            for msg in messages
        ]
        
        return message_list
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Message retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve messages"
        )