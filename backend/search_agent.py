"""Agentic search agent with query understanding, retrieval, and answer generation."""
import google.generativeai as genai
from typing import List, Dict, Tuple
from .store import VectorStore, DocumentChunk
from .indexer import DocumentIndexer
from .citation_agent import CitationAgent
from .config import settings


class SearchAgent:
    """Orchestrates the agentic search process."""
    
    def __init__(self, vector_store: VectorStore, indexer: DocumentIndexer):
        """Initialize search agent."""
        self.vector_store = vector_store
        self.indexer = indexer
        self.citation_agent = CitationAgent()
        
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required for text generation")
        
        genai.configure(api_key=settings.GEMINI_API_KEY)
        
        # Try model with fallbacks
        model_name = settings.LLM_MODEL
        fallback_models = ["gemini-1.5-flash", "gemini-pro", "gemini-1.5-pro"]
        fallback_models = [m for m in fallback_models if m != model_name]
        
        try:
            self.llm = genai.GenerativeModel(model_name)
        except Exception:
            model_loaded = False
            for fallback in fallback_models:
                try:
                    self.llm = genai.GenerativeModel(fallback)
                    model_loaded = True
                    break
                except Exception:
                    continue
            
            if not model_loaded:
                raise Exception(f"Could not load any Gemini model. Tried: {model_name} and {fallback_models}")
    
    def understand_query(self, query: str) -> Dict:
        """Understand and refine the query."""
        prompt = f"""Analyze the following search query and provide:
1. The main intent/keywords
2. Any specific information being sought
3. The type of answer expected (factual, explanatory, comparative, etc.)

Query: {query}

Provide a brief analysis in 1-2 sentences."""
        
        try:
            response = self.llm.generate_content(prompt)
            analysis = response.text.strip()
            return {
                "original_query": query,
                "analysis": analysis,
                "keywords": self._extract_keywords(query)
            }
        except Exception:
            return {
                "original_query": query,
                "analysis": "Query analysis unavailable",
                "keywords": self._extract_keywords(query)
            }
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords from query."""
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'what', 'where', 'when', 'why', 'how'}
        words = query.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords
    
    def retrieve_context(self, query: str, top_k: int = None) -> List[Tuple[DocumentChunk, float]]:
        """Retrieve relevant context chunks."""
        if top_k is None:
            top_k = settings.TOP_K
        
        query_embedding = self.indexer.generate_embedding(query)
        results = self.vector_store.search(query_embedding, top_k=top_k)
        return results
    
    def generate_answer(self, query: str, context_chunks: List[Tuple[DocumentChunk, float]]) -> str:
        """Generate answer from query and context."""
        if not context_chunks:
            return "I couldn't find relevant information to answer your question."
        
        # Limit context size
        max_chunk_length = settings.MAX_CHUNK_LENGTH
        limited_chunks = []
        total_length = 0
        
        for chunk, score in context_chunks[:settings.TOP_K]:
            truncated_content = chunk.content[:max_chunk_length]
            if len(chunk.content) > max_chunk_length:
                truncated_content += "..."
            
            chunk_text = f"Doc: {chunk.document_name}\n{truncated_content}"
            estimated_tokens = len(chunk_text) // 4
            
            if total_length + estimated_tokens > settings.MAX_CONTEXT_TOKENS:
                break
            
            limited_chunks.append((chunk, score, truncated_content))
            total_length += estimated_tokens
        
        context_parts = [f"[{chunk.document_name}]: {content}" for chunk, score, content in limited_chunks]
        context_text = "\n\n".join(context_parts)
        
        prompt = f"""Answer based on this context:

{context_text}

Q: {query}

Answer concisely using only the context above. If info is missing, say so."""
        
        try:
            response = self.llm.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"Error generating answer: {str(e)}"
    
    def generate_answer_stream(self, query: str, context_chunks: List[Tuple[DocumentChunk, float]], history: List[Dict] = None):
        """Generate answer with streaming support."""
        if not context_chunks:
            yield "I couldn't find relevant information to answer your question."
            return
        
        # Limit context size
        max_chunk_length = settings.MAX_CHUNK_LENGTH
        limited_chunks = []
        total_length = 0
        
        for chunk, score in context_chunks[:settings.TOP_K]:
            truncated_content = chunk.content[:max_chunk_length]
            if len(chunk.content) > max_chunk_length:
                truncated_content += "..."
            
            chunk_text = f"Doc: {chunk.document_name}\n{truncated_content}"
            estimated_tokens = len(chunk_text) // 4
            
            if total_length + estimated_tokens > settings.MAX_CONTEXT_TOKENS:
                break
            
            limited_chunks.append((chunk, score, truncated_content))
            total_length += estimated_tokens
        
        context_parts = [f"[{chunk.document_name}]: {content}" for chunk, score, content in limited_chunks]
        context_text = "\n\n".join(context_parts)
        
        # Build conversation context
        conversation_context = ""
        if history and len(history) > 0:
            recent_history = history[-4:]
            conv_parts = []
            for msg in recent_history:
                if msg.get("role") == "user":
                    conv_parts.append(f"Previous question: {msg.get('content', '')}")
                elif msg.get("role") == "assistant":
                    conv_parts.append(f"Previous answer: {msg.get('content', '')[:200]}...")
            if conv_parts:
                conversation_context = "\n\nPrevious conversation:\n" + "\n".join(conv_parts) + "\n"
        
        prompt = f"""Answer based on this context:{conversation_context}

{context_text}

Q: {query}

Answer concisely using only the context above. If info is missing, say so. Reference previous conversation if relevant."""
        
        try:
            response = self.llm.generate_content(prompt, stream=True)
            for chunk in response:
                text = None
                if hasattr(chunk, 'text') and chunk.text:
                    text = chunk.text
                elif hasattr(chunk, 'parts') and chunk.parts:
                    for part in chunk.parts:
                        if hasattr(part, 'text') and part.text:
                            text = part.text
                            break
                elif isinstance(chunk, str):
                    text = chunk
                
                if text:
                    yield text
        except Exception as e:
            yield f"Error generating answer: {str(e)}"
    
    def search(self, query: str) -> Dict:
        """Execute complete agentic search pipeline."""
        query_analysis = self.understand_query(query)
        context_results = self.retrieve_context(query)
        
        if not context_results:
            return {
                "answer": "I couldn't find relevant information to answer your question.",
                "citations": [],
                "sources": [],
                "query_analysis": query_analysis
            }
        
        source_chunks = [chunk for chunk, score in context_results]
        answer = self.generate_answer(query, context_results)
        cited_answer, citations = self.citation_agent.process_answer(answer, source_chunks)
        
        unique_docs = {}
        for chunk in source_chunks:
            if chunk.document_id not in unique_docs:
                unique_docs[chunk.document_id] = {
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name
                }
        
        return {
            "answer": cited_answer,
            "citations": citations,
            "sources": list(unique_docs.values()),
            "query_analysis": query_analysis,
            "retrieved_chunks": len(context_results)
        }
