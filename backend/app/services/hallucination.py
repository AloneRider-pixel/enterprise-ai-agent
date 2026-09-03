"""
Hallucination detection service.
Uses NLI-based approach to verify response faithfulness to retrieved context.
"""
import logging
import re
from typing import List, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


class HallucinationDetector:
    """
    Detects hallucinations by verifying that claims in the response
    are supported by the retrieved context.
    
    Uses a combination of:
    1. Sentence-level claim extraction
    2. Keyword/phrase overlap verification
    3. NLI-style entailment scoring (when model available)
    """

    def __init__(self):
        self._nli_model = None
        self.threshold = settings.hallucination_threshold

    def _load_nli_model(self):
        """Lazy-load NLI model for entailment detection."""
        if self._nli_model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._nli_model = CrossEncoder("cross-encoder/nli-deberta-v3-small")
                logger.info("NLI model loaded for hallucination detection")
            except Exception as e:
                logger.warning(f"NLI model unavailable: {e}. Using fallback detection.")
                self._nli_model = None

    async def detect(self, response: str, context: str) -> float:
        """
        Detect hallucination in a response given the source context.
        
        Returns a hallucination score between 0 and 1:
        - 0.0 = fully grounded (no hallucination)
        - 1.0 = complete hallucination
        
        Args:
            response: The generated response text
            context: The source context used for generation
        
        Returns:
            Hallucination score (0-1)
        """
        if not response or not context:
            return 0.0

        # Extract claims from response
        claims = self._extract_claims(response)
        
        if not claims:
            return 0.0

        # Score each claim
        claim_scores = []
        for claim in claims:
            score = await self._score_claim(claim, context)
            claim_scores.append(score)
        
        # Average hallucination score (higher = more hallucinated)
        avg_score = sum(claim_scores) / len(claim_scores) if claim_scores else 0.0
        
        logger.info(
            f"Hallucination detection: {len(claims)} claims, "
            f"avg_score={avg_score:.3f}, threshold={self.threshold}"
        )
        
        return avg_score

    def _extract_claims(self, text: str) -> List[str]:
        """Extract factual claims from response text."""
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        
        claims = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            
            # Filter out conversational/filler sentences
            filler_patterns = [
                r"^(i|we|you|please|sure|sorry|unfortunately|good|great|happy)",
                r"^(would you like|is there|can i|do you|let me)",
                r"^(here are|here is|below are)",
            ]
            
            is_filler = any(re.match(p, sentence, re.IGNORECASE) for p in filler_patterns)
            if not is_filler:
                claims.append(sentence)
        
        return claims[:10]  # Limit to 10 claims for efficiency

    async def _score_claim(self, claim: str, context: str) -> float:
        """
        Score a single claim for faithfulness.
        Returns 0.0 (grounded) to 1.0 (hallucinated).
        """
        # Try NLI-based scoring first
        try:
            self._load_nli_model()
            if self._nli_model is not None:
                return self._nli_score(claim, context)
        except Exception as e:
            logger.debug(f"NLI scoring failed: {e}")

        # Fallback: keyword overlap scoring
        return self._keyword_overlap_score(claim, context)

    def _nli_score(self, claim: str, context: str) -> float:
        """Score claim using NLI model."""
        # Extract relevant context sentences
        context_sentences = [s.strip() for s in re.split(r'[.!?]+', context) if len(s.strip()) > 10]
        
        if not context_sentences:
            return 0.5  # Unknown

        # Get best matching context sentence
        claim_words = set(claim.lower().split())
        best_sentence = ""
        best_overlap = 0
        
        for sent in context_sentences[:10]:
            sent_words = set(sent.lower().split())
            overlap = len(claim_words & sent_words)
            if overlap > best_overlap:
                best_overlap = overlap
                best_sentence = sent

        if not best_sentence:
            return 0.8  # No matching context

        # NLI prediction: entailment, contradiction, neutral
        labels = ["contradiction", "neutral", "entailment"]
        scores = self._nli_model.predict([(claim, best_sentence)])
        
        # Convert to hallucination score
        # High entailment = low hallucination
        # High contradiction = high hallucination
        contradiction_score = float(scores[0][0])  # P(contradiction)
        entailment_score = float(scores[0][2])     # P(entailment)
        
        hallucination_score = contradiction_score / (contradiction_score + entailment_score + 0.01)
        return min(1.0, max(0.0, hallucination_score))

    def _keyword_overlap_score(self, claim: str, context: str) -> float:
        """
        Fallback scoring using keyword overlap.
        Checks if key entities/phrases in the claim appear in context.
        """
        claim_words = set(claim.lower().split())
        context_words = set(context.lower().split())
        
        # Remove stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "and",
            "but", "or", "nor", "not", "so", "yet", "both", "either",
            "it", "its", "this", "that", "these", "those", "i", "we",
        }
        
        claim_content = claim_words - stop_words
        context_content = context_words - stop_words
        
        if not claim_content:
            return 0.0  # No content words, likely a filler sentence
        
        overlap = claim_content & context_content
        coverage = len(overlap) / len(claim_content) if claim_content else 0
        
        # Convert coverage to hallucination score
        # High coverage = grounded (low hallucination)
        hallucination_score = 1.0 - coverage
        
        return min(1.0, max(0.0, hallucination_score))


# Singleton
hallucination_detector = HallucinationDetector()
