"""
Evaluation module for comparing AI-generated mappings against
faculty reference (ground truth) mappings.

Computes:
- Overall accuracy, precision, recall, F1
- Per-class metrics (levels 0, 1, 2, 3)
- Per-CO accuracy
- Per-PO accuracy
- Agreement percentage
- Confusion matrix
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)

logger = logging.getLogger(__name__)


class EvaluationReport:
    """Structured evaluation results."""

    def __init__(self):
        self.accuracy: float = 0.0
        self.precision_macro: float = 0.0
        self.recall_macro: float = 0.0
        self.f1_macro: float = 0.0
        self.agreement_percentage: float = 0.0
        self.per_co_accuracy: Dict[str, float] = {}
        self.per_po_accuracy: Dict[str, float] = {}
        self.confusion_mat: Optional[np.ndarray] = None
        self.class_report: str = ""
        self.total_pairs: int = 0
        self.matched_pairs: int = 0
        self.method: str = ""

    def to_dict(self) -> Dict:
        return {
            "accuracy": round(self.accuracy, 4),
            "precision_macro": round(self.precision_macro, 4),
            "recall_macro": round(self.recall_macro, 4),
            "f1_macro": round(self.f1_macro, 4),
            "agreement_percentage": round(self.agreement_percentage, 2),
            "per_co_accuracy": {k: round(v, 4) for k, v in self.per_co_accuracy.items()},
            "per_po_accuracy": {k: round(v, 4) for k, v in self.per_po_accuracy.items()},
            "confusion_matrix": self.confusion_mat.tolist() if self.confusion_mat is not None else [],
            "classification_report": self.class_report,
            "total_pairs": self.total_pairs,
            "matched_pairs": self.matched_pairs,
            "method": self.method,
        }


def evaluate_mappings(
    ai_mappings: Dict[Tuple[str, str], int],
    reference_mappings: Dict[Tuple[str, str], int],
    method: str = "hybrid",
) -> EvaluationReport:
    """
    Evaluate AI mappings against faculty reference mappings.

    Args:
        ai_mappings: Dict mapping (co_code, po_pso_code) -> mapping_level
        reference_mappings: Dict mapping (co_code, po_pso_code) -> mapping_level
        method: Method name for the report.

    Returns:
        EvaluationReport with all computed metrics.
    """
    report = EvaluationReport()
    report.method = method

    # Find common pairs
    common_keys = set(ai_mappings.keys()).intersection(set(reference_mappings.keys()))

    if not common_keys:
        logger.warning("No common CO-PO pairs found between AI and reference mappings")
        return report

    report.total_pairs = len(common_keys)

    y_true = []
    y_pred = []

    # Group by CO and PO for per-item metrics
    co_results = defaultdict(lambda: {"true": [], "pred": []})
    po_results = defaultdict(lambda: {"true": [], "pred": []})

    for key in sorted(common_keys):
        co_code, po_pso_code = key
        true_level = reference_mappings[key]
        pred_level = ai_mappings[key]

        y_true.append(true_level)
        y_pred.append(pred_level)

        co_results[co_code]["true"].append(true_level)
        co_results[co_code]["pred"].append(pred_level)

        po_results[po_pso_code]["true"].append(true_level)
        po_results[po_pso_code]["pred"].append(pred_level)

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    # Overall metrics
    report.accuracy = float(accuracy_score(y_true, y_pred))

    # Use zero_division=0 to handle cases where a class is not present
    report.precision_macro = float(precision_score(
        y_true, y_pred, average='macro', zero_division=0, labels=[0, 1, 2, 3]
    ))
    report.recall_macro = float(recall_score(
        y_true, y_pred, average='macro', zero_division=0, labels=[0, 1, 2, 3]
    ))
    report.f1_macro = float(f1_score(
        y_true, y_pred, average='macro', zero_division=0, labels=[0, 1, 2, 3]
    ))

    # Agreement percentage (exact match)
    report.matched_pairs = int(np.sum(y_true == y_pred))
    report.agreement_percentage = (report.matched_pairs / report.total_pairs) * 100.0

    # Confusion matrix
    report.confusion_mat = confusion_matrix(y_true, y_pred, labels=[0, 1, 2, 3])

    # Classification report
    report.class_report = classification_report(
        y_true, y_pred,
        labels=[0, 1, 2, 3],
        target_names=["Level 0 (-)", "Level 1", "Level 2", "Level 3"],
        zero_division=0,
    )

    # Per-CO accuracy
    for co_code, data in co_results.items():
        co_true = np.array(data["true"])
        co_pred = np.array(data["pred"])
        report.per_co_accuracy[co_code] = float(accuracy_score(co_true, co_pred))

    # Per-PO accuracy
    for po_code, data in po_results.items():
        po_true = np.array(data["true"])
        po_pred = np.array(data["pred"])
        report.per_po_accuracy[po_code] = float(accuracy_score(po_true, po_pred))

    logger.info(
        f"Evaluation ({method}): Accuracy={report.accuracy:.4f}, "
        f"F1={report.f1_macro:.4f}, Agreement={report.agreement_percentage:.1f}%"
    )

    return report


def compare_methods(
    method_results: Dict[str, Dict[Tuple[str, str], int]],
    reference_mappings: Dict[Tuple[str, str], int],
) -> Dict[str, EvaluationReport]:
    """
    Compare multiple methods against the same reference mappings.

    Args:
        method_results: Dict mapping method_name -> {(co, po): level}
        reference_mappings: Ground truth mappings.

    Returns:
        Dict mapping method_name -> EvaluationReport
    """
    reports = {}
    for method_name, ai_mappings in method_results.items():
        reports[method_name] = evaluate_mappings(
            ai_mappings, reference_mappings, method=method_name
        )
    return reports


def format_comparison_table(reports: Dict[str, EvaluationReport]) -> str:
    """Format a comparison table for display."""
    header = f"{'Method':<20} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Agreement':>12}"
    separator = "-" * len(header)
    lines = [header, separator]

    for method, report in reports.items():
        line = (
            f"{method:<20} "
            f"{report.accuracy:>10.4f} "
            f"{report.precision_macro:>10.4f} "
            f"{report.recall_macro:>10.4f} "
            f"{report.f1_macro:>10.4f} "
            f"{report.agreement_percentage:>11.1f}%"
        )
        lines.append(line)

    return "\n".join(lines)
