"""
CO-PO Mapping Orchestrator.

Coordinates the full hybrid AI pipeline:
1. Text preprocessing
2. Embedding generation
3. Semantic similarity computation
4. Candidate generation
5. LLM contextual reasoning (or mock)
6. Validation

Supports three methods for research comparison:
- embedding_only: Similarity thresholds only
- llm_only: LLM reasoning without similarity pre-filtering
- hybrid: Embedding + LLM + validation (recommended)
"""

import logging
from typing import List, Dict, Optional, Tuple

from ai.preprocessor import preprocess_co, preprocess_po, get_enhanced_text
from ai.embeddings import compute_similarity_matrix
from ai.llm_reasoner import LLMProvider, MappingResult, get_llm_provider
from ai.validator import validate_mappings, fix_mapping_result, ValidationResult

logger = logging.getLogger(__name__)

# Default similarity threshold for candidate generation
DEFAULT_SIMILARITY_THRESHOLD = 0.12


def generate_mappings_hybrid(
    co_codes: List[str],
    co_texts: List[str],
    po_pso_codes: List[str],
    po_pso_texts: List[str],
    po_pso_types: List[str],
    context: Optional[str] = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    llm_provider: Optional[LLMProvider] = None,
) -> Tuple[List[MappingResult], ValidationResult, Dict]:
    """
    Full hybrid pipeline: Embedding → Similarity → LLM → Validation.
    """
    if llm_provider is None:
        llm_provider = get_llm_provider()

    # Step 1: Preprocess
    logger.info("Step 1: Preprocessing texts...")
    co_preprocessed = [preprocess_co(t) for t in co_texts]
    po_preprocessed = [preprocess_po(t) for t in po_pso_texts]

    co_enhanced = [get_enhanced_text(p) for p in co_preprocessed]
    po_enhanced = [get_enhanced_text(p) for p in po_preprocessed]

    # Step 2: Embedding & Similarity
    logger.info("Step 2: Computing semantic similarity...")
    similarity_matrix = compute_similarity_matrix(co_enhanced, po_enhanced)

    # Step 3: Candidate Generation (Threshold + Top-K per CO)
    logger.info("Step 3: Identifying candidates...")
    candidates = []
    candidate_set = set()
    all_results = []

    # Define core accreditation outcomes that must always be evaluated by the LLM
    CORE_ACCREDITATION_POS = {"PO1", "PO2", "PO3", "PO4", "PO5", "PO7", "PO8", "PO11"}

    # For each CO, include core engineering outcomes plus high-similarity/top-k candidates
    for i, co_code in enumerate(co_codes):
        sorted_pos = sorted(range(len(po_pso_codes)), key=lambda j: float(similarity_matrix[i][j]), reverse=True)
        top_k_indices = set(sorted_pos[:4])

        co_verbs = set(co_preprocessed[i].get("action_verbs", []))
        co_concepts = set(co_preprocessed[i].get("key_concepts", []))

        for j, po_pso_code in enumerate(po_pso_codes):
            sim_score = float(similarity_matrix[i][j])
            po_verbs = set(po_preprocessed[j].get("action_verbs", []))
            po_concepts = set(po_preprocessed[j].get("key_concepts", []))

            has_keyword_overlap = bool((co_verbs & po_verbs) or (co_concepts & po_concepts))
            is_core_po = po_pso_code.upper() in CORE_ACCREDITATION_POS or po_pso_code.upper().startswith("PSO")

            if is_core_po or sim_score >= similarity_threshold or j in top_k_indices or (has_keyword_overlap and sim_score >= 0.05):
                candidates.append((i, j, sim_score))
                candidate_set.add((i, j))
            else:
                # Below threshold and not in core set: assign level 0
                all_results.append(MappingResult(
                    co_code=co_code,
                    po_pso_code=po_pso_code,
                    mapping_level=0,
                    confidence=round(max(0.05, 1.0 - sim_score), 2),
                    reason=(
                        f"No meaningful correlation detected between course outcome "
                        f"and {po_pso_code} (similarity: {sim_score:.2f})."
                    ),
                    evidence=[],
                    similarity_score=sim_score,
                ))

    logger.info(
        f"Identified {len(candidates)} candidates from "
        f"{len(co_codes) * len(po_pso_codes)} total pairs"
    )


    # Step 4: LLM Reasoning for candidates
    logger.info("Step 4: LLM reasoning on candidates...")
    candidate_dicts = [
        {
            "co_code": co_codes[i],
            "co_text": co_texts[i],
            "po_pso_code": po_pso_codes[j],
            "po_pso_text": po_pso_texts[j],
            "similarity_score": sim_score,
        }
        for i, j, sim_score in candidates
    ]
    batch_results = llm_provider.reason_candidates_batch(candidate_dicts, context=context)
    all_results.extend(batch_results)

    # Step 5: Validation
    logger.info("Step 5: Validating results...")
    validation = validate_mappings(
        all_results,
        expected_co_codes=co_codes,
        expected_po_pso_codes=po_pso_codes,
    )

    # Fix any invalid results
    final_results = []
    for result in all_results:
        fixed = fix_mapping_result(result)
        final_results.append(fixed)

    metadata = {
        "method": "hybrid",
        "total_pairs": len(co_codes) * len(po_pso_codes),
        "candidates": len(candidates),
        "similarity_threshold": similarity_threshold,
        "co_count": len(co_codes),
        "po_pso_count": len(po_pso_codes),
    }

    return final_results, validation, metadata


def generate_mappings_embedding_only(
    co_codes: List[str],
    co_texts: List[str],
    po_pso_codes: List[str],
    po_pso_texts: List[str],
    po_pso_types: List[str],
    context: Optional[str] = None,
) -> Tuple[List[MappingResult], ValidationResult, Dict]:
    """
    Baseline 1: Embedding-only method.

    Uses similarity thresholds to determine mapping levels:
    - sim >= 0.6  → level 3
    - sim >= 0.4  → level 2
    - sim >= 0.25 → level 1
    - sim <  0.25 → level 0
    """
    logger.info("Running embedding-only method...")

    co_preprocessed = [preprocess_co(t) for t in co_texts]
    po_preprocessed = [preprocess_po(t) for t in po_pso_texts]

    co_enhanced = [get_enhanced_text(p) for p in co_preprocessed]
    po_enhanced = [get_enhanced_text(p) for p in po_preprocessed]

    similarity_matrix = compute_similarity_matrix(co_enhanced, po_enhanced)

    results = []
    for i, co_code in enumerate(co_codes):
        for j, po_pso_code in enumerate(po_pso_codes):
            sim_score = float(similarity_matrix[i][j])

            if sim_score >= 0.6:
                level = 3
            elif sim_score >= 0.4:
                level = 2
            elif sim_score >= 0.25:
                level = 1
            else:
                level = 0

            confidence = min(0.95, sim_score + 0.2) if level > 0 else max(0.05, 1.0 - sim_score)

            results.append(MappingResult(
                co_code=co_code,
                po_pso_code=po_pso_code,
                mapping_level=level,
                confidence=round(confidence, 2),
                reason=f"Embedding-only: cosine similarity = {sim_score:.4f}. Level assigned by threshold.",
                evidence=[],
                similarity_score=sim_score,
            ))

    validation = validate_mappings(results, co_codes, po_pso_codes)

    metadata = {
        "method": "embedding_only",
        "total_pairs": len(results),
        "co_count": len(co_codes),
        "po_pso_count": len(po_pso_codes),
    }

    return results, validation, metadata


def generate_mappings_llm_only(
    co_codes: List[str],
    co_texts: List[str],
    po_pso_codes: List[str],
    po_pso_texts: List[str],
    po_pso_types: List[str],
    context: Optional[str] = None,
    llm_provider: Optional[LLMProvider] = None,
) -> Tuple[List[MappingResult], ValidationResult, Dict]:
    """
    Baseline 2: LLM-only method.

    Sends every CO-PO pair to the LLM without similarity pre-filtering.
    Similarity score is set to 0.0 (not computed).
    """
    if llm_provider is None:
        llm_provider = get_llm_provider()

    logger.info("Running LLM-only method...")

    results = []
    for i, co_code in enumerate(co_codes):
        for j, po_pso_code in enumerate(po_pso_codes):
            result = llm_provider.reason_mapping(
                co_code=co_code,
                co_text=co_texts[i],
                po_pso_code=po_pso_code,
                po_pso_text=po_pso_texts[j],
                similarity_score=0.0,
                context=context,
            )
            results.append(result)

    # Fix results
    results = [fix_mapping_result(r) for r in results]

    validation = validate_mappings(results, co_codes, po_pso_codes)

    metadata = {
        "method": "llm_only",
        "total_pairs": len(results),
        "co_count": len(co_codes),
        "po_pso_count": len(po_pso_codes),
    }

    return results, validation, metadata


def generate_mappings(
    method: str,
    co_codes: List[str],
    co_texts: List[str],
    po_pso_codes: List[str],
    po_pso_texts: List[str],
    po_pso_types: List[str],
    context: Optional[str] = None,
) -> Tuple[List[MappingResult], ValidationResult, Dict]:
    """
    Main entry point: generate mappings using the specified method.

    Args:
        method: One of "hybrid", "embedding_only", "llm_only"
        co_codes, co_texts: Course outcomes
        po_pso_codes, po_pso_texts, po_pso_types: Program outcomes
        context: Optional course context

    Returns:
        Tuple of (results, validation, metadata)
    """
    if method == "embedding_only":
        return generate_mappings_embedding_only(
            co_codes, co_texts, po_pso_codes, po_pso_texts, po_pso_types, context
        )
    elif method == "llm_only":
        return generate_mappings_llm_only(
            co_codes, co_texts, po_pso_codes, po_pso_texts, po_pso_types, context
        )
    else:
        return generate_mappings_hybrid(
            co_codes, co_texts, po_pso_codes, po_pso_texts, po_pso_types, context
        )
