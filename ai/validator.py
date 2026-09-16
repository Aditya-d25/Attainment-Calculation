"""
Validation component for AI mapping outputs.

Checks for:
- Invalid mapping levels
- Invalid confidence values
- Missing COs/POs
- Duplicate mappings
- Malformed JSON
- Empty/unsupported explanations
- Inconsistent output
"""

import json
import logging
from typing import List, Dict, Tuple, Optional

from ai.llm_reasoner import MappingResult

logger = logging.getLogger(__name__)

VALID_LEVELS = {0, 1, 2, 3}


class ValidationError:
    """Represents a single validation issue."""

    def __init__(self, error_type: str, message: str, co_code: str = "", po_pso_code: str = ""):
        self.error_type = error_type
        self.message = message
        self.co_code = co_code
        self.po_pso_code = po_pso_code

    def to_dict(self) -> Dict:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "co_code": self.co_code,
            "po_pso_code": self.po_pso_code,
        }


class ValidationResult:
    """Result of validating mapping outputs."""

    def __init__(self):
        self.valid_mappings: List[MappingResult] = []
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "valid_mapping_count": len(self.valid_mappings),
        }


def validate_mapping_level(result: MappingResult) -> List[ValidationError]:
    """Validate that mapping level is within valid range."""
    errors = []
    if result.mapping_level not in VALID_LEVELS:
        errors.append(ValidationError(
            "INVALID_LEVEL",
            f"Mapping level {result.mapping_level} is not valid. Must be 0, 1, 2, or 3.",
            result.co_code,
            result.po_pso_code,
        ))
    return errors


def validate_confidence(result: MappingResult) -> List[ValidationError]:
    """Validate that confidence is within valid range."""
    errors = []
    if not (0.0 <= result.confidence <= 1.0):
        errors.append(ValidationError(
            "INVALID_CONFIDENCE",
            f"Confidence {result.confidence} is out of range [0.0, 1.0].",
            result.co_code,
            result.po_pso_code,
        ))
    return errors


def validate_reason(result: MappingResult) -> List[ValidationError]:
    """Validate that a meaningful reason is provided."""
    warnings = []
    if not result.reason or len(result.reason.strip()) < 10:
        warnings.append(ValidationError(
            "EMPTY_REASON",
            f"Mapping {result.co_code}-{result.po_pso_code} has an empty or very short explanation.",
            result.co_code,
            result.po_pso_code,
        ))
    return warnings


def validate_evidence(result: MappingResult) -> List[ValidationError]:
    """Validate evidence list."""
    warnings = []
    if result.mapping_level > 0 and (not result.evidence or len(result.evidence) == 0):
        warnings.append(ValidationError(
            "MISSING_EVIDENCE",
            f"Mapping {result.co_code}-{result.po_pso_code} has level {result.mapping_level} but no supporting evidence.",
            result.co_code,
            result.po_pso_code,
        ))
    return warnings


def validate_consistency(result: MappingResult) -> List[ValidationError]:
    """Check for logical consistency between mapping level and confidence."""
    warnings = []

    # High level but low confidence is suspicious
    if result.mapping_level == 3 and result.confidence < 0.5:
        warnings.append(ValidationError(
            "INCONSISTENT",
            f"Mapping {result.co_code}-{result.po_pso_code} has level 3 but confidence {result.confidence:.2f} is very low.",
            result.co_code,
            result.po_pso_code,
        ))

    # No mapping but high confidence is also suspicious
    if result.mapping_level == 0 and result.confidence > 0.8 and result.similarity_score > 0.5:
        warnings.append(ValidationError(
            "INCONSISTENT",
            f"Mapping {result.co_code}-{result.po_pso_code} has level 0 but high similarity ({result.similarity_score:.2f}).",
            result.co_code,
            result.po_pso_code,
        ))

    return warnings


def validate_completeness(
    results: List[MappingResult],
    expected_co_codes: List[str],
    expected_po_pso_codes: List[str],
) -> List[ValidationError]:
    """Check that all expected CO-PO pairs have mappings."""
    errors = []

    result_pairs = {(r.co_code, r.po_pso_code) for r in results}

    for co_code in expected_co_codes:
        for po_pso_code in expected_po_pso_codes:
            if (co_code, po_pso_code) not in result_pairs:
                errors.append(ValidationError(
                    "MISSING_MAPPING",
                    f"No mapping found for {co_code}-{po_pso_code}.",
                    co_code,
                    po_pso_code,
                ))

    return errors


def validate_duplicates(results: List[MappingResult]) -> List[ValidationError]:
    """Check for duplicate CO-PO pairs."""
    errors = []
    seen = set()

    for result in results:
        pair = (result.co_code, result.po_pso_code)
        if pair in seen:
            errors.append(ValidationError(
                "DUPLICATE_MAPPING",
                f"Duplicate mapping for {result.co_code}-{result.po_pso_code}.",
                result.co_code,
                result.po_pso_code,
            ))
        seen.add(pair)

    return errors


def validate_mappings(
    results: List[MappingResult],
    expected_co_codes: Optional[List[str]] = None,
    expected_po_pso_codes: Optional[List[str]] = None,
) -> ValidationResult:
    """
    Full validation pipeline for a list of mapping results.

    Args:
        results: List of MappingResult objects from the AI pipeline.
        expected_co_codes: Expected CO codes for completeness check.
        expected_po_pso_codes: Expected PO/PSO codes for completeness check.

    Returns:
        ValidationResult with valid mappings, errors, and warnings.
    """
    validation = ValidationResult()

    # Check for duplicates across all results
    validation.errors.extend(validate_duplicates(results))

    # Check completeness if expected codes are provided
    if expected_co_codes and expected_po_pso_codes:
        validation.errors.extend(
            validate_completeness(results, expected_co_codes, expected_po_pso_codes)
        )

    # Validate each individual result
    for result in results:
        individual_errors = []

        individual_errors.extend(validate_mapping_level(result))
        individual_errors.extend(validate_confidence(result))

        if individual_errors:
            validation.errors.extend(individual_errors)
        else:
            # Only add to valid if no hard errors
            validation.valid_mappings.append(result)

        # Warnings don't invalidate the mapping
        validation.warnings.extend(validate_reason(result))
        validation.warnings.extend(validate_evidence(result))
        validation.warnings.extend(validate_consistency(result))

    if validation.errors:
        logger.warning(
            f"Validation found {len(validation.errors)} errors "
            f"and {len(validation.warnings)} warnings"
        )
    else:
        logger.info(
            f"Validation passed: {len(validation.valid_mappings)} valid mappings, "
            f"{len(validation.warnings)} warnings"
        )

    return validation


def fix_mapping_result(result: MappingResult) -> MappingResult:
    """
    Attempt to fix common issues in a mapping result.

    - Clamps mapping level to valid range
    - Clamps confidence to [0.0, 1.0]
    - Provides default reason if missing
    """
    fixed_level = max(0, min(3, result.mapping_level))
    fixed_confidence = max(0.0, min(1.0, result.confidence))
    fixed_reason = result.reason if result.reason and len(result.reason.strip()) >= 5 else "Auto-corrected: insufficient explanation from AI."
    fixed_evidence = result.evidence if result.evidence else []

    return MappingResult(
        co_code=result.co_code,
        po_pso_code=result.po_pso_code,
        mapping_level=fixed_level,
        confidence=fixed_confidence,
        reason=fixed_reason,
        evidence=fixed_evidence,
        similarity_score=result.similarity_score,
    )
