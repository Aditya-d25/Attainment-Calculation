"""Tests for the validator module."""

import pytest
from ai.validator import (
    validate_mapping_level,
    validate_confidence,
    validate_duplicates,
    validate_completeness,
    validate_mappings,
    fix_mapping_result,
    ValidationResult,
)
from ai.llm_reasoner import MappingResult


def make_result(co="CO1", po="PO1", level=2, confidence=0.8, reason="Test reason", evidence=None):
    return MappingResult(
        co_code=co, po_pso_code=po, mapping_level=level,
        confidence=confidence, reason=reason,
        evidence=evidence or ["test"], similarity_score=0.5,
    )


class TestValidateMappingLevel:
    def test_valid_levels(self):
        for level in [0, 1, 2, 3]:
            result = make_result(level=level)
            errors = validate_mapping_level(result)
            assert len(errors) == 0

    def test_invalid_level(self):
        result = make_result(level=5)
        errors = validate_mapping_level(result)
        assert len(errors) == 1
        assert errors[0].error_type == "INVALID_LEVEL"

    def test_negative_level(self):
        result = make_result(level=-1)
        errors = validate_mapping_level(result)
        assert len(errors) == 1


class TestValidateConfidence:
    def test_valid_confidence(self):
        for conf in [0.0, 0.5, 1.0]:
            result = make_result(confidence=conf)
            errors = validate_confidence(result)
            assert len(errors) == 0

    def test_invalid_confidence(self):
        result = make_result(confidence=1.5)
        errors = validate_confidence(result)
        assert len(errors) == 1

    def test_negative_confidence(self):
        result = make_result(confidence=-0.1)
        errors = validate_confidence(result)
        assert len(errors) == 1


class TestValidateDuplicates:
    def test_no_duplicates(self):
        results = [make_result("CO1", "PO1"), make_result("CO1", "PO2")]
        errors = validate_duplicates(results)
        assert len(errors) == 0

    def test_duplicates(self):
        results = [make_result("CO1", "PO1"), make_result("CO1", "PO1")]
        errors = validate_duplicates(results)
        assert len(errors) == 1
        assert errors[0].error_type == "DUPLICATE_MAPPING"


class TestValidateCompleteness:
    def test_complete(self):
        results = [
            make_result("CO1", "PO1"),
            make_result("CO1", "PO2"),
        ]
        errors = validate_completeness(results, ["CO1"], ["PO1", "PO2"])
        assert len(errors) == 0

    def test_missing(self):
        results = [make_result("CO1", "PO1")]
        errors = validate_completeness(results, ["CO1"], ["PO1", "PO2"])
        assert len(errors) == 1
        assert errors[0].error_type == "MISSING_MAPPING"


class TestValidateMappings:
    def test_valid_set(self):
        results = [
            make_result("CO1", "PO1", 2, 0.8),
            make_result("CO1", "PO2", 1, 0.6),
        ]
        validation = validate_mappings(results, ["CO1"], ["PO1", "PO2"])
        assert validation.is_valid
        assert len(validation.valid_mappings) == 2

    def test_invalid_set(self):
        results = [
            make_result("CO1", "PO1", 5, 0.8),  # Invalid level
        ]
        validation = validate_mappings(results)
        assert not validation.is_valid


class TestFixMappingResult:
    def test_clamps_level(self):
        result = make_result(level=5)
        fixed = fix_mapping_result(result)
        assert fixed.mapping_level == 3

    def test_clamps_confidence(self):
        result = make_result(confidence=1.5)
        fixed = fix_mapping_result(result)
        assert fixed.confidence == 1.0

    def test_provides_default_reason(self):
        result = make_result(reason="")
        fixed = fix_mapping_result(result)
        assert len(fixed.reason) > 5
