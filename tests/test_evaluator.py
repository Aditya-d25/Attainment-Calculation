"""Tests for the evaluator module."""

import pytest
import numpy as np
from ai.evaluator import evaluate_mappings, compare_methods, EvaluationReport


class TestEvaluateMappings:
    def test_perfect_agreement(self):
        ai = {("CO1", "PO1"): 2, ("CO1", "PO2"): 1, ("CO1", "PO3"): 0}
        ref = {("CO1", "PO1"): 2, ("CO1", "PO2"): 1, ("CO1", "PO3"): 0}

        report = evaluate_mappings(ai, ref)

        assert report.accuracy == 1.0
        assert report.agreement_percentage == 100.0
        assert report.matched_pairs == 3

    def test_no_agreement(self):
        ai = {("CO1", "PO1"): 0, ("CO1", "PO2"): 3}
        ref = {("CO1", "PO1"): 3, ("CO1", "PO2"): 0}

        report = evaluate_mappings(ai, ref)

        assert report.accuracy == 0.0
        assert report.agreement_percentage == 0.0

    def test_partial_agreement(self):
        ai = {("CO1", "PO1"): 2, ("CO1", "PO2"): 1, ("CO1", "PO3"): 3}
        ref = {("CO1", "PO1"): 2, ("CO1", "PO2"): 2, ("CO1", "PO3"): 3}

        report = evaluate_mappings(ai, ref)

        assert report.accuracy == pytest.approx(2.0 / 3.0, rel=1e-3)
        assert report.matched_pairs == 2

    def test_per_co_accuracy(self):
        ai = {
            ("CO1", "PO1"): 2, ("CO1", "PO2"): 1,
            ("CO2", "PO1"): 3, ("CO2", "PO2"): 0,
        }
        ref = {
            ("CO1", "PO1"): 2, ("CO1", "PO2"): 1,
            ("CO2", "PO1"): 3, ("CO2", "PO2"): 1,
        }

        report = evaluate_mappings(ai, ref)

        assert report.per_co_accuracy["CO1"] == 1.0
        assert report.per_co_accuracy["CO2"] == 0.5

    def test_per_po_accuracy(self):
        ai = {("CO1", "PO1"): 2, ("CO2", "PO1"): 3}
        ref = {("CO1", "PO1"): 2, ("CO2", "PO1"): 3}

        report = evaluate_mappings(ai, ref)
        assert report.per_po_accuracy["PO1"] == 1.0

    def test_confusion_matrix(self):
        ai = {("CO1", "PO1"): 2}
        ref = {("CO1", "PO1"): 2}

        report = evaluate_mappings(ai, ref)
        assert report.confusion_mat is not None
        assert report.confusion_mat.shape == (4, 4)

    def test_no_common_pairs(self):
        ai = {("CO1", "PO1"): 2}
        ref = {("CO2", "PO2"): 1}

        report = evaluate_mappings(ai, ref)
        assert report.total_pairs == 0

    def test_empty_inputs(self):
        report = evaluate_mappings({}, {})
        assert report.total_pairs == 0


class TestCompareMethods:
    def test_compares_two_methods(self):
        ref = {("CO1", "PO1"): 2, ("CO1", "PO2"): 1}

        method_results = {
            "method_a": {("CO1", "PO1"): 2, ("CO1", "PO2"): 1},
            "method_b": {("CO1", "PO1"): 1, ("CO1", "PO2"): 1},
        }

        reports = compare_methods(method_results, ref)

        assert len(reports) == 2
        assert reports["method_a"].accuracy == 1.0
        assert reports["method_b"].accuracy == 0.5
