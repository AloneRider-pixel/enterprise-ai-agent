"""
RAG response generator with citation tracking.
Generates grounded responses using retrieved context with source references.
"""
import json
import logging
from typing import AsyncGenerator, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

SYSTEM_PROMPT = """You are an expert enterprise support agent. Your job is to help customers 
by answering questions using the provided context from our knowledge base.

RULES:
1. ONLY use information from the provided context to answer questions.
2. If the context doesn't contain enough information, say so honestly.
3. ALWAYS cite your sources using [Source X] format where X is the source number.
4. Be clear, concise, and professional.
5. If you're unsure, recommend the customer speak with a human agent.
6. Never make up information or speculate beyond what the context provides.

CITATION FORMAT:
- Reference sources inline: "According to our policy [Source 1]..."
- Multiple sources: "[Source 1][Source 3]"
- Always include at least one citation when using context information."""


class RAGGenerator:
    """
    Generates grounded responses with citations from retrieved context.
    Supports both streaming and non-streaming generation.
    """

    def __init__(self):
        self.model = settings.openai_model
        self.temperature = 0.1  # Low temperature for factual responses
        self.max_tokens = 1024

    def _build_context(self, chunks: List[Dict]) -> Tuple[str, List[Dict]]:
        """
        Build context string from retrieved chunks.
        Returns formatted context and source citation list.
        """
        sources = []
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            source = {
                "source_number": i,
                "chunk_id": chunk.get("chunk_id", ""),
                "document_id": chunk.get("document_id", ""),
                "content": chunk["content"],
                "score": chunk.get("score", 0),
                "metadata": chunk.get("metadata", {}),
            }
            sources.append(source)
            context_parts.append(
                f"[Source {i}] (Score: {chunk.get('score', 0):.3f})\n{chunk['content']}"
            )

        context = "\n\n---\n\n".join(context_parts)
        return context, sources

    def _build_messages(
        self,
        query: str,
        context: str,
        conversation_history: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """Build the message list for the LLM call."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add conversation history for multi-turn context
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 3 turns
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        # Add the RAG context and query
        user_message = f"""CONTEXT FROM KNOWLEDGE BASE:
{context}

---

CUSTOMER QUESTION: {query}

Please answer the customer's question using ONLY the context above. Include source citations."""

        messages.append({"role": "user", "content": user_message})
        return messages

    async def generate(
        self,
        query: str,
        chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Generate a complete response with citations.
        
        Returns dict with response, citations, and token usage.
        """
        if not chunks:
            return {
                "response": "I couldn't find relevant information to answer your question. Would you like me to connect you with a human agent?",
                "citations": [],
                "tokens": {"input": 0, "output": 0},
            }

        context, sources = self._build_context(chunks)
        messages = self._build_messages(query, context, conversation_history)

        try:
            response = await openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content
            usage = response.usage

            return {
                "response": content,
                "citations": sources,
                "tokens": {
                    "input": usage.prompt_tokens if usage else 0,
                    "output": usage.completion_tokens if usage else 0,
                    "total": usage.total_tokens if usage else 0,
                },
            }
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return {
                "response": "I apologize, but I'm experiencing technical difficulties. Please try again or contact a human agent.",
                "citations": [],
                "tokens": {"input": 0, "output": 0, "total": 0},
                "error": str(e),
            }

    async def generate_stream(
        self,
        query: str,
        chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response tokens via Server-Sent Events.
        
        Yields SSE-formatted strings for each token chunk.
        """
        if not chunks:
            yield f"data: {json.dumps({'event': 'token', 'content': 'I couldn\'t find relevant information. Would you like me to connect you with a human agent?'})}\n\n"
            yield f"data: {json.dumps({'event': 'done', 'citations': []})}\n\n"
            return

        context, sources = self._build_context(chunks)
        messages = self._build_messages(query, context, conversation_history)

        try:
            # Send citations first
            yield f"data: {json.dumps({'event': 'citations', 'sources': [{'source_number': s['source_number'], 'document_id': s['document_id'], 'score': s['score']} for s in sources]})}\n\n"

            # Stream response tokens
            stream = await openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )

            full_response = []
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response.append(token)
                    yield f"data: {json.dumps({'event': 'token', 'content': token})}\n\n"

            # Send done event with metadata
            yield f"data: {json.dumps({'event': 'done', 'citations': sources})}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': 'An error occurred during streaming.'})}\n\n"

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate API cost based on token usage."""
        input_cost = input_tokens * settings.gpt4o_mini_input_price
        output_cost = output_tokens * settings.gpt4o_mini_output_price
        return input_cost + output_cost


# Singleton
rag_generator = RAGGenerator()
