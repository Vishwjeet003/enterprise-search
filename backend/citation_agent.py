"""Citation agent for mapping answer text to source documents."""
import re
from typing import List, Dict, Tuple
from .store import DocumentChunk


class CitationAgent:
    """Maps answer text to source document chunks and generates citations."""
    
    def find_citation_matches(self, answer_text: str, source_chunks: List[DocumentChunk]) -> List[Dict]:
        """Find which chunks are likely cited in the answer text."""
        sentences = re.split(r'[.!?]+', answer_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        chunk_scores = {}
        for chunk in source_chunks:
            score = 0
            chunk_words = set(chunk.content.lower().split())
            
            for sentence in sentences:
                sentence_words = set(sentence.lower().split())
                significant_overlap = len([w for w in chunk_words if len(w) > 3 and w in sentence_words])
                if significant_overlap > 0:
                    score += significant_overlap
            
            if score > 0:
                chunk_scores[chunk.id] = (chunk, score)
        
        sorted_chunks = sorted(chunk_scores.values(), key=lambda x: x[1], reverse=True)
        
        citation_map = {}
        citation_num = 1
        
        for chunk, score in sorted_chunks:
            if chunk.document_id not in citation_map:
                citation_map[chunk.document_id] = {
                    "number": citation_num,
                    "chunk": chunk,
                    "document_name": chunk.document_name
                }
                citation_num += 1
        
        return list(citation_map.values())
    
    def insert_citations(self, answer_text: str, citations: List[Dict]) -> Tuple[str, List[Dict]]:
        """Insert citation markers as markdown links into answer text."""
        if not citations:
            return answer_text, []
        
        doc_to_citation = {}
        citation_list = []
        
        for cit in citations:
            doc_id = cit["chunk"].document_id
            if doc_id not in doc_to_citation:
                citation_num = cit["number"]
                web_url = cit["chunk"].web_url or f"https://drive.google.com/file/d/{doc_id}/view"
                doc_to_citation[doc_id] = (citation_num, web_url)
                citation_list.append({
                    "number": citation_num,
                    "document_name": cit["document_name"],
                    "document_id": doc_id,
                    "web_url": web_url
                })
        
        sentences = re.split(r'([.!?]+)', answer_text)
        cited_sentences = set()
        
        for cit in citations:
            chunk = cit["chunk"]
            chunk_keywords = set([w.lower() for w in chunk.content.split() if len(w) > 4])
            
            for i, sentence in enumerate(sentences):
                if i in cited_sentences:
                    continue
                
                sentence_words = set([w.lower() for w in sentence.split() if len(w) > 4])
                overlap = len(chunk_keywords & sentence_words)
                
                if overlap >= 2:
                    citation_num, web_url = doc_to_citation[chunk.document_id]
                    if not re.search(r'\[\[?\d+\]\]?\(', sentence):
                        sentences[i] = sentence.rstrip() + f" [[{citation_num}]]({web_url})"
                        cited_sentences.add(i)
        
        cited_answer = ''.join(sentences)
        
        # Ensure at least one citation per paragraph
        paragraphs = cited_answer.split('\n\n')
        final_paragraphs = []
        
        for para in paragraphs:
            if para.strip() and not re.search(r'\[\[\d+\]\]', para):
                if citation_list:
                    first_citation = citation_list[0]
                    citation_num = first_citation["number"]
                    web_url = first_citation["web_url"]
                    sentences_in_para = re.split(r'([.!?]+)', para)
                    if len(sentences_in_para) > 1:
                        sentences_in_para[0] = sentences_in_para[0].rstrip() + f" [[{citation_num}]]({web_url})"
                        para = ''.join(sentences_in_para)
            final_paragraphs.append(para)
        
        return '\n\n'.join(final_paragraphs), citation_list
    
    def process_answer(self, answer_text: str, source_chunks: List[DocumentChunk]) -> Tuple[str, List[Dict]]:
        """Process answer to add citations."""
        citations = self.find_citation_matches(answer_text, source_chunks)
        cited_answer, citation_list = self.insert_citations(answer_text, citations)
        return cited_answer, citation_list
