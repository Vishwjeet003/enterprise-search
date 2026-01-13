"""In-memory vector store for embeddings."""
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DocumentChunk:
    """Represents a chunk of a document with its embedding."""
    id: str
    document_id: str
    document_name: str
    content: str
    embedding: List[float]
    chunk_index: int
    start_char: int
    end_char: int
    web_url: Optional[str] = None  # Google Drive web view URL
    
    def __hash__(self):
        """Make DocumentChunk hashable by using its ID."""
        return hash(self.id)
    
    def __eq__(self, other):
        """Compare DocumentChunks by ID."""
        if not isinstance(other, DocumentChunk):
            return False
        return self.id == other.id


class VectorStore:
    """In-memory vector store using cosine similarity."""
    
    def __init__(self):
        """Initialize empty vector store."""
        self.chunks: List[DocumentChunk] = []
        self.embeddings_matrix: np.ndarray = None
    
    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Add document chunks to the store."""
        self.chunks.extend(chunks)
        self._update_embeddings_matrix()
    
    def _update_embeddings_matrix(self) -> None:
        """Update the embeddings matrix for efficient similarity search."""
        if not self.chunks:
            self.embeddings_matrix = np.array([])
            return
        
        embeddings = [chunk.embedding for chunk in self.chunks]
        self.embeddings_matrix = np.array(embeddings)
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        """Search for similar chunks using cosine similarity."""
        if not self.chunks or len(self.chunks) == 0:
            return []
        
        query_vector = np.array(query_embedding)
        
        # Normalize query vector
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []
        query_vector = query_vector / query_norm
        
        # Normalize embeddings matrix
        norms = np.linalg.norm(self.embeddings_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        normalized_embeddings = self.embeddings_matrix / norms
        
        # Compute cosine similarities
        similarities = np.dot(normalized_embeddings, query_vector)
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Return chunks with similarity scores
        results = []
        for idx in top_indices:
            if similarities[idx] > 0:  # Only return positive similarities
                results.append((self.chunks[idx], float(similarities[idx])))
        
        return results
    
    def get_chunks_by_document(self, document_id: str) -> List[DocumentChunk]:
        """Get all chunks for a specific document."""
        return [chunk for chunk in self.chunks if chunk.document_id == document_id]
    
    def clear(self) -> None:
        """Clear all chunks from the store."""
        self.chunks = []
        self.embeddings_matrix = None
    
    def get_stats(self) -> Dict:
        """Get statistics about the store."""
        document_ids = set(chunk.document_id for chunk in self.chunks)
        return {
            "total_chunks": len(self.chunks),
            "total_documents": len(document_ids),
            "avg_chunks_per_doc": len(self.chunks) / len(document_ids) if document_ids else 0
        }

