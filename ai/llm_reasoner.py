"""
LLM-based contextual reasoning for CO-PO mapping.

Provides an abstraction layer supporting:
- Google Gemini API
- Mock provider (rule-based, for development/testing)
- Extensible to OpenAI, Anthropic, etc.

The LLM receives CO text, PO text, semantic similarity,
and optional course context. It returns structured JSON
with mapping_level, confidence, reason, and evidence.
"""

import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from ai.preprocessor import extract_action_verbs, extract_key_concepts

logger = logging.getLogger(__name__)


class MappingResult:
    """Structured result from LLM reasoning."""

    def __init__(
        self,
        co_code: str,
        po_pso_code: str,
        mapping_level: int,
        confidence: float,
        reason: str,
        evidence: List[str],
        similarity_score: float = 0.0,
    ):
        self.co_code = co_code
        self.po_pso_code = po_pso_code
        self.mapping_level = mapping_level
        self.confidence = confidence
        self.reason = reason
        self.evidence = evidence
        self.similarity_score = similarity_score

    def to_dict(self) -> Dict:
        return {
            "co_code": self.co_code,
            "po_pso_code": self.po_pso_code,
            "mapping_level": self.mapping_level,
            "confidence": self.confidence,
            "reason": self.reason,
            "evidence": self.evidence,
            "similarity_score": self.similarity_score,
        }


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def reason_mapping(
        self,
        co_code: str,
        co_text: str,
        po_pso_code: str,
        po_pso_text: str,
        similarity_score: float,
        context: Optional[str] = None,
    ) -> MappingResult:
        """
        Determine the CO-PO/PSO mapping using contextual reasoning.

        Returns a MappingResult with level, confidence, reason, and evidence.
        """
        pass


# -------------------------
# Prompt Template
# -------------------------

MAPPING_PROMPT = """You are an expert in outcome-based education. Your task is to determine the strength of the relationship between a Course Outcome (CO) and a Program Outcome (PO/PSO).

## Course Outcome
Code: {co_code}
Description: "{co_text}"

## Program Outcome
Code: {po_pso_code}
Description: "{po_pso_text}"

## Semantic Similarity Score
{similarity_score:.4f} (cosine similarity from embedding model)

{context_section}

## Task
Analyze the educational relationship between this CO and PO/PSO. Consider:
1. Does the CO directly or indirectly support achieving the PO/PSO?
2. What specific skills, knowledge, or competencies overlap?
3. What action verbs and concepts provide evidence of the relationship?

## Mapping Levels
- 3 = Strong relationship: The CO directly and substantially contributes to the PO/PSO
- 2 = Moderate relationship: The CO meaningfully supports the PO/PSO through indirect or partial contribution
- 1 = Weak relationship: The CO has a minor or tangential connection to the PO/PSO
- 0 = No meaningful relationship: Insufficient evidence of any connection

## Rules
- Do NOT assign a high level without clear evidence
- A high semantic similarity alone does NOT guarantee a strong mapping
- Consider Bloom's taxonomy alignment between CO and PO
- Be conservative: if evidence is weak or ambiguous, assign a lower level

## Response Format
Respond with ONLY a JSON object (no markdown, no code fences):
{{"mapping_level": <0|1|2|3>, "confidence": <0.0-1.0>, "reason": "<2-3 sentence explanation>", "evidence": ["<keyword1>", "<keyword2>", ...]}}
"""


# -------------------------
# Gemini Provider
# -------------------------

class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai.GenerativeModel(self.model)
        return self._client

    def reason_mapping(
        self,
        co_code: str,
        co_text: str,
        po_pso_code: str,
        po_pso_text: str,
        similarity_score: float,
        context: Optional[str] = None,
    ) -> MappingResult:
        client = self._get_client()

        context_section = ""
        if context:
            context_section = f"## Additional Course Context\n{context}\n"

        prompt = MAPPING_PROMPT.format(
            co_code=co_code,
            co_text=co_text,
            po_pso_code=po_pso_code,
            po_pso_text=po_pso_text,
            similarity_score=similarity_score,
            context_section=context_section,
        )

        try:
            response = client.generate_content(prompt)
            result_text = response.text.strip()
            parsed = self._parse_response(result_text)

            return MappingResult(
                co_code=co_code,
                po_pso_code=po_pso_code,
                mapping_level=parsed.get("mapping_level", 0),
                confidence=parsed.get("confidence", 0.0),
                reason=parsed.get("reason", "No explanation provided."),
                evidence=parsed.get("evidence", []),
                similarity_score=similarity_score,
            )
        except Exception as e:
            logger.error(f"Gemini API error for {co_code}-{po_pso_code}: {e}")
            # Intelligent fallback based on semantic similarity when LLM is rate limited
            if similarity_score >= 0.5:
                lvl = 3
            elif similarity_score >= 0.35:
                lvl = 2
            elif similarity_score >= 0.2:
                lvl = 1
            else:
                lvl = 0

            return MappingResult(
                co_code=co_code,
                po_pso_code=po_pso_code,
                mapping_level=lvl,
                confidence=round(max(0.3, min(0.85, similarity_score + 0.1)), 2),
                reason=f"Semantic fallback (LLM rate limit): score {similarity_score:.2f}",
                evidence=[],
                similarity_score=similarity_score,
            )

    def _parse_response(self, text: str) -> Dict:
        """Parse JSON from LLM response, handling markdown fences."""
        # Remove markdown code fences if present
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON object from text
            match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning(f"Failed to parse LLM response: {text[:200]}")
            return {}


# -------------------------
# Mock Provider
# -------------------------

class MockProvider(LLMProvider):
    """
    Rule-based mock provider for development and testing.

    Uses semantic similarity thresholds and keyword overlap
    to generate deterministic mapping results.
    """

    # PO keywords for keyword-matching heuristic
    PO_KEYWORDS = {
        "PO1": ["engineering", "knowledge", "science", "mathematics", "fundamentals",
                 "principles", "apply"],
        "PO2": ["problem", "analysis", "analyze", "identify", "formulate",
                 "research", "literature", "complex"],
        "PO3": ["design", "develop", "solution", "system", "component",
                 "process", "meet", "needs", "specification"],
        "PO4": ["investigate", "complex", "analysis", "interpretation",
                 "data", "experiment", "synthesis", "information"],
        "PO5": ["modern", "tool", "technique", "resource", "engineering",
                 "IT", "prediction", "modeling", "software"],
        "PO6": ["society", "social", "legal", "cultural", "contextual",
                 "knowledge", "responsible", "engineering"],
        "PO7": ["environment", "sustainable", "development", "impact",
                 "professional", "practice"],
        "PO8": ["ethics", "professional", "responsibility", "norms",
                 "practice", "engineering"],
        "PO9": ["individual", "team", "member", "leader", "diverse",
                 "multidisciplinary", "teamwork", "collaborate"],
        "PO10": ["communicate", "communication", "effective", "write",
                  "present", "report", "document", "instruction"],
        "PO11": ["project", "management", "finance", "plan", "manage",
                  "engineer", "member", "leader"],
        "PSO1": ["computer", "science", "engineering", "foundation",
                  "apply", "fundamental", "core"],
        "PSO2": ["software", "develop", "application", "programming",
                  "technology", "modern", "tool", "implement"],
        "PSO3": ["research", "innovation", "creative", "novel",
                  "emerging", "technology", "interdisciplinary"],
    }

    def reason_mapping(
        self,
        co_code: str,
        co_text: str,
        po_pso_code: str,
        po_pso_text: str,
        similarity_score: float,
        context: Optional[str] = None,
    ) -> MappingResult:
        # Extract features
        co_verbs = set(extract_action_verbs(co_text))
        co_concepts = set(extract_key_concepts(co_text))
        po_concepts = set(extract_key_concepts(po_pso_text))

        # Keyword matching
        po_keywords = set(self.PO_KEYWORDS.get(po_pso_code, []))
        co_words = set(co_text.lower().split())
        keyword_overlap = co_words.intersection(po_keywords)
        concept_overlap = co_concepts.intersection(po_concepts)

        # Combined scoring
        # TF-IDF similarity can be low, and strict keyword matching is often sparse.
        # We boost the similarity and use softer thresholds to simulate realistic 
        # LLM reasoning that can infer connections between concepts.
        keyword_score = min(1.0, len(keyword_overlap) / max(len(po_keywords) * 0.3, 1))
        concept_score = min(1.0, len(concept_overlap) / max(len(po_concepts) * 0.5, 1))

        # Weighted combination
        combined_score = (
            0.5 * similarity_score +
            0.3 * keyword_score +
            0.2 * concept_score
        )

        # Determine mapping level (adjusted to be more generous to match real-world mappings)
        if combined_score >= 0.28:
            mapping_level = 3
        elif combined_score >= 0.15:
            mapping_level = 2
        elif combined_score >= 0.06:
            mapping_level = 1
        else:
            mapping_level = 0

        # Generate confidence
        confidence = min(0.95, combined_score + 0.3) if mapping_level > 0 else max(0.05, 1.0 - combined_score)

        # Build evidence list
        evidence = sorted(list(keyword_overlap.union(concept_overlap)))[:8]

        # Generate reason
        if mapping_level == 0:
            reason = (
                f"The CO does not contain sufficient evidence of activities "
                f"related to {po_pso_code} ({po_pso_text}). "
                f"Semantic similarity is {similarity_score:.2f}, "
                f"which is below the threshold for a meaningful relationship."
            )
        elif mapping_level == 1:
            reason = (
                f"The CO has a minor connection to {po_pso_code}. "
                f"Semantic similarity ({similarity_score:.2f}) and keyword overlap "
                f"suggest a tangential relationship through concepts: "
                f"{', '.join(evidence[:4]) if evidence else 'indirect association'}."
            )
        elif mapping_level == 2:
            reason = (
                f"The CO moderately supports {po_pso_code}. "
                f"The semantic similarity ({similarity_score:.2f}) combined with "
                f"overlapping concepts ({', '.join(evidence[:4])}) indicates "
                f"a meaningful indirect contribution."
            )
        else:
            reason = (
                f"The CO strongly contributes to {po_pso_code}. "
                f"High semantic similarity ({similarity_score:.2f}) and strong "
                f"keyword evidence ({', '.join(evidence[:4])}) demonstrate "
                f"a direct and substantial relationship."
            )

        return MappingResult(
            co_code=co_code,
            po_pso_code=po_pso_code,
            mapping_level=mapping_level,
            confidence=round(confidence, 2),
            reason=reason,
            evidence=evidence,
            similarity_score=similarity_score,
        )


# -------------------------
# Provider Factory
# -------------------------

def get_llm_provider() -> LLMProvider:
    """
    Get the configured LLM provider.

    Uses MOCK_MODE, LLM_PROVIDER, LLM_API_KEY, and LLM_MODEL
    from environment variables.
    """
    mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"

    if mock_mode:
        logger.info("Using MockProvider (MOCK_MODE=true)")
        return MockProvider()

    provider_name = os.getenv("LLM_PROVIDER", "gemini").lower()
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "gemini-3.6-flash")

    if not api_key:
        logger.warning("No LLM_API_KEY set, falling back to MockProvider")
        return MockProvider()

    if provider_name == "gemini":
        return GeminiProvider(api_key=api_key, model=model)
    else:
        logger.warning(f"Unknown LLM_PROVIDER: {provider_name}, using MockProvider")
        return MockProvider()
