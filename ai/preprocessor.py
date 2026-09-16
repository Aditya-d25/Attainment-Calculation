"""
Text preprocessing for CO and PO/PSO descriptions.

Normalizes text while preserving meaningful educational terminology
and action verbs that are critical for determining relationship strength.
"""

import re
from typing import List, Dict, Set


# Bloom's Taxonomy action verbs — important for CO-PO mapping
ACTION_VERBS = {
    # Remember
    "define", "list", "recall", "recognize", "identify", "name", "state",
    # Understand
    "describe", "explain", "interpret", "classify", "summarize", "compare",
    "discuss", "distinguish", "illustrate",
    # Apply
    "apply", "implement", "use", "execute", "solve", "demonstrate",
    "calculate", "compute", "operate", "practice",
    # Analyze
    "analyze", "differentiate", "examine", "investigate", "categorize",
    "organize", "deconstruct", "contrast",
    # Evaluate
    "evaluate", "assess", "justify", "critique", "judge", "appraise",
    "argue", "defend", "support",
    # Create
    "create", "design", "develop", "construct", "produce", "formulate",
    "propose", "plan", "compose", "build", "generate", "invent",
}

# Engineering and technical keywords to preserve
TECHNICAL_TERMS = {
    "algorithm", "data structure", "programming", "software", "hardware",
    "database", "network", "security", "system", "architecture",
    "machine learning", "artificial intelligence", "optimization",
    "simulation", "modeling", "testing", "verification", "validation",
    "requirement", "specification", "protocol", "framework",
    "object-oriented", "complexity", "efficiency", "scalability",
    "ethics", "sustainability", "environment", "society", "safety",
    "communication", "teamwork", "leadership", "management", "finance",
    "lifelong learning", "professional", "innovation", "research",
    "engineering", "technology", "science", "mathematics",
}

# Common boilerplate phrases to remove
BOILERPLATE_PATTERNS = [
    r"^(the\s+)?student(s)?\s+(will|shall|should|would|can|is\s+able\s+to)\s+",
    r"^(the\s+)?learner(s)?\s+(will|shall|should|would|can|is\s+able\s+to)\s+",
    r"^(at\s+the\s+end\s+of\s+(the|this)\s+(course|program|module)\s*,?\s*)",
    r"^(upon\s+completion\s+(of\s+(the|this)\s+(course|program|module))?\s*,?\s*)",
    r"^(ability|able)\s+to\s+",
]


def normalize_text(text: str) -> str:
    """
    Normalize text while preserving meaningful content.

    - Strips whitespace
    - Normalizes case
    - Removes extra spaces and punctuation noise
    - Preserves technical terminology and action verbs
    """
    if not text or not text.strip():
        return ""

    # Strip and normalize whitespace
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)

    # Normalize case to lowercase
    text = text.lower()

    # Remove trailing periods, semicolons
    text = text.rstrip('.;,')

    # Normalize common unicode characters
    text = text.replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')

    return text


def remove_boilerplate(text: str) -> str:
    """Remove common boilerplate phrasing from COs."""
    normalized = normalize_text(text)
    for pattern in BOILERPLATE_PATTERNS:
        normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
    return normalized.strip()


def extract_action_verbs(text: str) -> List[str]:
    """Extract Bloom's Taxonomy action verbs from text."""
    normalized = normalize_text(text)
    words = set(re.findall(r'\b[a-z]+\b', normalized))
    found = sorted(words.intersection(ACTION_VERBS))
    return found


def extract_key_concepts(text: str) -> List[str]:
    """Extract key technical concepts and noun phrases from text."""
    normalized = normalize_text(text)
    concepts = []

    # Check multi-word technical terms
    for term in TECHNICAL_TERMS:
        if term in normalized:
            concepts.append(term)

    # Also extract single meaningful words (nouns, adjectives)
    # that are not common stopwords
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "shall", "should", "would", "may", "might", "can", "could",
        "and", "or", "but", "if", "then", "else", "when", "where",
        "how", "what", "which", "who", "whom", "this", "that", "these",
        "those", "to", "of", "in", "for", "on", "with", "at", "by",
        "from", "as", "into", "through", "during", "before", "after",
        "above", "below", "between", "under", "over", "about", "up",
        "down", "out", "off", "not", "no", "nor", "so", "too", "very",
        "just", "also", "its", "it", "they", "them", "their", "he",
        "she", "his", "her", "our", "your", "my", "we", "us", "me",
        "able", "ability", "student", "students", "learner", "course",
        "using", "use", "used",
    }

    words = re.findall(r'\b[a-z]{3,}\b', normalized)
    for word in words:
        if word not in stopwords and word not in concepts:
            concepts.append(word)

    return concepts


def preprocess_co(co_text: str) -> Dict:
    """
    Full preprocessing pipeline for a Course Outcome.

    Returns:
        Dict with normalized text, action verbs, and key concepts.
    """
    return {
        "original": co_text,
        "normalized": normalize_text(co_text),
        "cleaned": remove_boilerplate(co_text),
        "action_verbs": extract_action_verbs(co_text),
        "key_concepts": extract_key_concepts(co_text),
    }


def preprocess_po(po_text: str) -> Dict:
    """
    Full preprocessing pipeline for a Program Outcome / PSO.

    Returns:
        Dict with normalized text and key concepts.
    """
    return {
        "original": po_text,
        "normalized": normalize_text(po_text),
        "cleaned": remove_boilerplate(po_text),
        "action_verbs": extract_action_verbs(po_text),
        "key_concepts": extract_key_concepts(po_text),
    }


def preprocess_batch(texts: List[str]) -> List[Dict]:
    """Preprocess a batch of texts."""
    return [preprocess_co(t) for t in texts]


def get_enhanced_text(preprocessed: Dict) -> str:
    """
    Create an enhanced text representation that emphasizes
    action verbs and key concepts for better embedding quality.
    """
    parts = [preprocessed["cleaned"]]

    if preprocessed["action_verbs"]:
        parts.append("Key actions: " + ", ".join(preprocessed["action_verbs"]))

    return ". ".join(parts)
