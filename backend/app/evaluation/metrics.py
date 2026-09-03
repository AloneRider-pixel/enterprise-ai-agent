"""
RAG evaluation metrics.
Implements faithfulness, answer relevance, and context recall measurements.
"""
import logging
import re
from typing import List, Set

logger = logging.getLogger(__name__)


# Common stop words for content analysis
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "and", "but", "or", "nor", "not", "so", "yet",
    "both", "either", "it", "its", "this", "that", "these", "those",
    "i", "we", "you", "he", "she", "they", "me", "him", "her", "us",
    "my", "your", "his", "our", "their", "what", "which", "who", "when",
    "where", "why", "how", "all", "each", "every", "any", "some", "no",
}


def compute_faithfulness(response: str, context: str) -> float:
    """
    Compute faithfulness score: how much of the response is grounded in context.
    
    Uses keyword overlap analysis to estimate what proportion of the response's
    factual claims are supported by the source context.
    
    Returns:
        Score between 0.0 (not faithful) and 1.0 (fully faithful)
    """
    if not response or not context:
        return 0.0
    
    # Extract content words from response
    response_words = _extract_content_words(response)
    context_words = _extract_content_words(context)
    
    if not response_words:
        return 1.0  # No content to evaluate
    
    # Measure how many response words appear in context
    grounded_words = response_words & context_words
    
    # Calculate faithfulness as proportion of response grounded in context
    faithfulness = len(grounded_words) / len(response_words)
    
    # Bonus for key phrases matching
    response_phrases = _extract_phrases(response)
    context_lower = context.lower()
    
    phrase_matches = sum(1 for phrase in response_phrases if phrase in context_lower)
    if response_phrases:
        phrase_score = phrase_matches / len(response_phrases)
        # Weighted combination
        faithfulness = 0.6 * faithfulness + 0.4 * phrase_score
    
    return round(min(1.0, max(0.0, faithfulness)), 4)


def compute_answer_relevance(question: str, answer: str) -> float:
    """
    Compute answer relevance: how well the answer addresses the question.
    
    Measures keyword overlap between question and answer,
    plus semantic indicators of direct answering.
    
    Returns:
        Score between 0.0 (irrelevant) and 1.0 (fully relevant)
    """
    if not question or not answer:
        return 0.0
    
    # Content words from question
    question_words = _extract_content_words(question)
    answer_words = _extract_content_words(answer)
    
    if not question_words or not answer_words:
        return 0.5  # Default for empty content
    
    # Direct keyword overlap
    overlap = question_words & answer_words
    word_overlap_score = len(overlap) / len(question_words) if question_words else 0
    
    # Check for answer-like patterns (indicators of direct response)
    direct_answer_patterns = [
        r"the (answer|policy|process|plan|method|step)",
        r"(yes|no|sure|certainly|absolutely)",
        r"you can|you need to|you should",
        r"(is|are|was|were) \d+",
        r"\$\d+",  # Price mentions
    ]
    
    answer_lower = answer.lower()
    direct_indicators = sum(1 for p in direct_answer_patterns if re.search(p, answer_lower))
    directness_score = min(1.0, direct_indicators * 0.3)
    
    # Check for off-topic indicators
    off_topic_patterns = [
        r"i (don't|do not) know",
        r"i can't help",
        r"that's not (something|i can)",
        r"unrelated",
    ]
    
    off_topic = any(re.search(p, answer_lower) for p in off_topic_patterns)
    off_topic_penalty = 0.5 if off_topic else 1.0
    
    # Combine scores
    relevance = (0.6 * word_overlap_score + 0.4 * directness_score) * off_topic_penalty
    
    return round(min(1.0, max(0.0, relevance)), 4)


def compute_context_recall(ground_truth: str, retrieved_context: str) -> float:
    """
    Compute context recall: how much of the ground truth is covered by retrieved context.
    
    Measures whether the retrieved context contains the information
    needed to answer the question (as defined by the ground truth).
    
    Returns:
        Score between 0.0 (no recall) and 1.0 (full recall)
    """
    if not ground_truth or not retrieved_context:
        return 0.0
    
    # Extract key information from ground truth
    gt_words = _extract_content_words(ground_truth)
    ctx_words = _extract_content_words(retrieved_context)
    
    if not gt_words:
        return 1.0  # Nothing to recall
    
    # Measure how many ground truth words are found in context
    recalled_words = gt_words & ctx_words
    word_recall = len(recalled_words) / len(gt_words) if gt_words else 0
    
    # Check for key phrases from ground truth in context
    gt_phrases = _extract_phrases(ground_truth)
    ctx_lower = retrieved_context.lower()
    
    phrase_matches = sum(1 for phrase in gt_phrases if phrase in ctx_lower)
    phrase_recall = phrase_matches / len(gt_phrases) if gt_phrases else 0
    
    # Check for numerical/price information recall
    gt_numbers = set(re.findall(r'\d+(?:\.\d+)?', ground_truth))
    ctx_numbers = set(re.findall(r'\d+(?:\.\d+)?', retrieved_context))
    
    number_recall = 0.0
    if gt_numbers:
        recalled_numbers = gt_numbers & ctx_numbers
        number_recall = len(recalled_numbers) / len(gt_numbers)
    
    # Weighted combination
    recall = 0.5 * word_recall + 0.3 * phrase_recall + 0.2 * number_recall
    
    return round(min(1.0, max(0.0, recall)), 4)


def compute_context_precision(query: str, retrieved_context: str) -> float:
    """
    Compute context precision: how much of the retrieved context is relevant to the query.
    
    Returns:
        Score between 0.0 (no precision) and 1.0 (full precision)
    """
    if not query or not retrieved_context:
        return 0.0
    
    query_words = _extract_content_words(query)
    ctx_words = _extract_content_words(retrieved_context)
    
    if not ctx_words:
        return 0.0
    
    # Proportion of context words that are relevant to the query
    relevant_words = query_words & ctx_words
    precision = len(relevant_words) / len(ctx_words) if ctx_words else 0
    
    return round(min(1.0, max(0.0, precision)), 4)


def _extract_content_words(text: str) -> Set[str]:
    """Extract content words (non-stop words) from text."""
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
    return {w for w in words if w not in STOP_WORDS}


def _extract_phrases(text: str, min_length: int = 3) -> List[str]:
    """Extract meaningful phrases (2-3 word combinations) from text."""
    words = [w for w in re.findall(r'\b[a-zA-Z]{2,}\b', text.lower()) if w not in STOP_WORDS]
    
    phrases = []
    for i in range(len(words) - 1):
        phrase = f"{words[i]} {words[i + 1]}"
        if len(phrase) >= min_length:
            phrases.append(phrase)
    
    return phrases[:20]  # Limit for efficiency
