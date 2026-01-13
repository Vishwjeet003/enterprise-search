"""FastAPI backend for enterprise search application."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn
import json
import asyncio
from google.oauth2.credentials import Credentials

from .config import settings
from .drive_connector import DriveConnector
from .store import VectorStore
from .indexer import DocumentIndexer
from .search_agent import SearchAgent


app = FastAPI(title="Enterprise Search API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
drive_connector = DriveConnector(
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    redirect_uri=settings.GOOGLE_REDIRECT_URI
)
vector_store = VectorStore()
indexer = DocumentIndexer(vector_store)
search_agent = SearchAgent(vector_store, indexer)

# In-memory storage
user_sessions: Dict[str, Credentials] = {}
chat_history: Dict[str, List[Dict]] = {}


class SearchRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = "default"


class SearchResponse(BaseModel):
    answer: str
    citations: List[Dict]
    sources: List[Dict]
    query_analysis: Optional[Dict] = None
    retrieved_chunks: Optional[int] = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Enterprise Search API", "status": "running"}


@app.get("/auth/authorize")
async def authorize():
    """Get OAuth authorization URL."""
    try:
        auth_url = drive_connector.get_authorization_url()
        return {"authorization_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating auth URL: {str(e)}")


@app.get("/auth/callback")
async def auth_callback(code: str, state: Optional[str] = None):
    """Handle OAuth callback."""
    try:
        drive_connector.authenticate(code)
        session_id = "default_session"
        user_sessions[session_id] = drive_connector.credentials
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?authenticated=true")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Authentication failed: {str(e)}")


@app.post("/auth/set-credentials")
async def set_credentials(credentials_data: dict):
    """Set credentials from frontend."""
    try:
        creds = Credentials(
            token=credentials_data.get("token"),
            refresh_token=credentials_data.get("refresh_token"),
            token_uri=credentials_data.get("token_uri"),
            client_id=credentials_data.get("client_id"),
            client_secret=credentials_data.get("client_secret")
        )
        drive_connector.set_credentials(creds)
        return {"status": "success", "message": "Credentials set"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error setting credentials: {str(e)}")


@app.get("/drive/documents")
async def list_documents():
    """List documents from Google Drive."""
    try:
        if not drive_connector.service:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        documents = drive_connector.list_documents(
            mime_types=settings.FILE_TYPES,
            max_files=settings.MAX_FILES_TO_INDEX
        )
        return {
            "documents": documents, 
            "count": len(documents),
            "limit": settings.MAX_FILES_TO_INDEX,
            "file_types": settings.FILE_TYPES
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")


@app.post("/index/documents/stream")
async def index_documents_stream():
    """Index documents with streaming progress updates."""
    async def generate():
        try:
            if not drive_connector.service:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Not authenticated'})}\n\n"
                return
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Clearing existing index...'})}\n\n"
            await asyncio.sleep(0.1)
            vector_store.clear()
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Fetching documents from Google Drive...'})}\n\n"
            await asyncio.sleep(0.1)
            
            documents = drive_connector.list_documents(
                mime_types=settings.FILE_TYPES,
                max_files=settings.MAX_FILES_TO_INDEX
            )
            
            if not documents:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No PDF documents found'})}\n\n"
                return
            
            yield f"data: {json.dumps({'type': 'progress', 'total': len(documents), 'current': 0})}\n\n"
            
            indexed_count = 0
            indexed_docs = []
            
            for idx, doc in enumerate(documents, 1):
                try:
                    doc_name = doc["name"]
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Processing: {doc_name} ({idx}/{len(documents)})'})}\n\n"
                    await asyncio.sleep(0.1)
                    
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Extracting text from {doc_name}...'})}\n\n"
                    content = drive_connector.get_document_content(doc["id"], doc["mimeType"])
                    
                    if len(content) > 50000:
                        content = content[:50000] + "... [truncated]"
                    
                    yield f"data: {json.dumps({'type': 'status', 'message': f'Generating embeddings for {doc_name}...'})}\n\n"
                    web_url = doc.get("webViewLink", f"https://drive.google.com/file/d/{doc['id']}/view")
                    chunk_count = indexer.index_document(
                        document_id=doc["id"],
                        document_name=doc["name"],
                        content=content,
                        web_url=web_url
                    )
                    
                    indexed_count += 1
                    indexed_docs.append({
                        "id": doc["id"],
                        "name": doc["name"],
                        "chunks": chunk_count
                    })
                    
                    yield f"data: {json.dumps({'type': 'progress', 'total': len(documents), 'current': idx, 'document': doc_name, 'chunks': chunk_count})}\n\n"
                    
                except Exception as e:
                    doc_name = doc.get("name", "Unknown")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Error indexing {doc_name}'})}\n\n"
                    continue
            
            stats = vector_store.get_stats()
            yield f"data: {json.dumps({'type': 'complete', 'indexed': indexed_count, 'documents': indexed_docs, 'stats': stats})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Perform agentic search (non-streaming)."""
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        result = search_agent.search(request.query)
        return SearchResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@app.post("/search/stream")
async def search_stream(request: SearchRequest):
    """Perform agentic search with streaming response."""
    async def generate():
        try:
            if not request.query or not request.query.strip():
                yield f"data: {json.dumps({'error': 'Query cannot be empty'})}\n\n"
                return
            
            conv_id = request.conversation_id or "default"
            if conv_id not in chat_history:
                chat_history[conv_id] = []
            
            history = chat_history[conv_id]
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Understanding query...'})}\n\n"
            await asyncio.sleep(0.1)
            query_analysis = search_agent.understand_query(request.query)
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Retrieving relevant documents...'})}\n\n"
            await asyncio.sleep(0.1)
            context_results = search_agent.retrieve_context(request.query)
            
            if not context_results:
                error_message = "I couldn't find relevant information to answer your question."
                yield f"data: {json.dumps({'type': 'answer', 'text': error_message})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                chat_history[conv_id].append({"role": "user", "content": request.query})
                chat_history[conv_id].append({"role": "assistant", "content": error_message, "citations": [], "sources": []})
                return
            
            source_chunks = [chunk for chunk, score in context_results]
            yield f"data: {json.dumps({'type': 'status', 'message': f'Found {len(context_results)} relevant sections. Generating answer...'})}\n\n"
            await asyncio.sleep(0.1)
            
            yield f"data: {json.dumps({'type': 'answer_start'})}\n\n"
            full_answer = ""
            
            for text_chunk in search_agent.generate_answer_stream(request.query, context_results, history):
                full_answer += text_chunk
                yield f"data: {json.dumps({'type': 'answer', 'text': text_chunk})}\n\n"
                await asyncio.sleep(0.01)
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Adding citations...'})}\n\n"
            await asyncio.sleep(0.1)
            cited_answer, citations = search_agent.citation_agent.process_answer(full_answer, source_chunks)
            
            unique_docs = {}
            for chunk in source_chunks:
                if chunk.document_id not in unique_docs:
                    unique_docs[chunk.document_id] = {
                        "document_id": chunk.document_id,
                        "document_name": chunk.document_name,
                        "web_url": chunk.web_url or f"https://drive.google.com/file/d/{chunk.document_id}/view"
                    }
            
            chat_history[conv_id].append({"role": "user", "content": request.query})
            chat_history[conv_id].append({
                "role": "assistant",
                "content": cited_answer,
                "citations": citations,
                "sources": list(unique_docs.values())
            })
            
            yield f"data: {json.dumps({'type': 'answer_complete', 'text': cited_answer, 'citations': citations, 'sources': list(unique_docs.values())})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/stats")
async def get_stats():
    """Get vector store statistics."""
    stats = vector_store.get_stats()
    return {"stats": stats}


@app.get("/chat/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    """Get chat history for a conversation."""
    if conversation_id not in chat_history:
        return {"history": []}
    return {"history": chat_history[conversation_id]}


@app.delete("/chat/history/{conversation_id}")
async def clear_chat_history(conversation_id: str):
    """Clear chat history for a conversation."""
    if conversation_id in chat_history:
        chat_history[conversation_id] = []
    return {"message": "Chat history cleared"}


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=settings.BACKEND_PORT, reload=True)
