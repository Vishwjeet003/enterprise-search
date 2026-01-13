"""Document indexing with intelligent chunking and embedding generation."""
import re
from typing import List, Dict, Optional
from .store import DocumentChunk, VectorStore
from .config import settings

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None


class DocumentIndexer:
    """Handles document chunking and embedding generation."""
    
    def __init__(self, vector_store: VectorStore):
        """Initialize indexer with vector store."""
        self.vector_store = vector_store
        self.local_embedding_model = None
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not SentenceTransformer:
            raise ImportError("sentence-transformers is required. Install it with: pip install sentence-transformers")
        
        try:
            import torch
            # Verify PyTorch is functional
            _ = torch.tensor([1.0])
            self.local_embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            raise ImportError("PyTorch is required. Install it with: pip install torch>=2.1.0")
        except Exception as e:
            raise Exception(f"Failed to initialize embedding model: {str(e)}")
    
    def chunk_text(self, text: str, chunk_size: int = None, chunk_overlap: int = None) -> List[Dict]:
        """Intelligently chunk text into overlapping segments."""
        if chunk_size is None:
            chunk_size = settings.CHUNK_SIZE
        if chunk_overlap is None:
            chunk_overlap = settings.CHUNK_OVERLAP
        
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) <= chunk_size:
            return [{"text": text, "start": 0, "end": len(text)}]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            if end >= len(text):
                chunks.append({
                    "text": text[start:],
                    "start": start,
                    "end": len(text)
                })
                break
            
            # Break at sentence boundary
            last_period = text.rfind('.', start, end)
            last_newline = text.rfind('\n', start, end)
            break_point = max(last_period, last_newline)
            
            if break_point > start:
                end = break_point + 1
            
            chunks.append({
                "text": text[start:end].strip(),
                "start": start,
                "end": end
            })
            
            start = max(start + 1, end - chunk_overlap)
        
        return chunks
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using local sentence-transformers model."""
        if not self.local_embedding_model:
            raise Exception("Embedding model not initialized")
        
        if not text or not text.strip():
            text = " "
        
        try:
            embedding = self.local_embedding_model.encode(text, convert_to_numpy=True, show_progress_bar=False)
            return embedding.tolist()
        except Exception as e:
            raise Exception(f"Error generating embedding: {str(e)}")
    
    def index_document(self, document_id: str, document_name: str, content: str, web_url: Optional[str] = None) -> int:
        """Index a document by chunking and generating embeddings."""
        chunks_data = self.chunk_text(content)
        document_chunks = []
        
        for idx, chunk_data in enumerate(chunks_data):
            try:
                embedding = self.generate_embedding(chunk_data["text"])
                
                chunk = DocumentChunk(
                    id=f"{document_id}_chunk_{idx}",
                    document_id=document_id,
                    document_name=document_name,
                    content=chunk_data["text"],
                    embedding=embedding,
                    chunk_index=idx,
                    start_char=chunk_data["start"],
                    end_char=chunk_data["end"],
                    web_url=web_url
                )
                document_chunks.append(chunk)
            except Exception:
                continue
        
        if document_chunks:
            self.vector_store.add_chunks(document_chunks)
        
        return len(document_chunks)
