"""
Mapping Service — Business logic orchestration layer.

Coordinates between the AI pipeline, database, and API layer.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session

from models import (
    Subject, CourseOutcome, ProgramOutcome, ProgramSpecificOutcome,
    AIMappingResult, ReferenceMappingEntry, MappingEvaluation,
    FacultyDecision, FrameworkOutcome,
)
from ai.mapper import generate_mappings
from ai.evaluator import evaluate_mappings, EvaluationReport

logger = logging.getLogger(__name__)


def get_subject_data(db: Session, subject_id: int) -> Dict:
    """Load all COs, POs, PSOs for a subject."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise ValueError(f"Subject {subject_id} not found")

    cos = db.query(CourseOutcome).filter(
        CourseOutcome.subject_id == subject_id
    ).order_by(CourseOutcome.co_code).all()

    # Framework outcomes are canonical for a whole stream.  Fall back to the
    # legacy subject records only for courses created before frameworks.
    if subject.framework_id:
        framework_outcomes = db.query(FrameworkOutcome).filter(
            FrameworkOutcome.framework_id == subject.framework_id
        ).order_by(FrameworkOutcome.outcome_type, FrameworkOutcome.outcome_code).all()
        pos = [row for row in framework_outcomes if row.outcome_type == "PO"]
        psos = [row for row in framework_outcomes if row.outcome_type == "PSO"]
    else:
        pos = db.query(ProgramOutcome).filter(
            ProgramOutcome.subject_id == subject_id
        ).order_by(ProgramOutcome.po_code).all()
        psos = db.query(ProgramSpecificOutcome).filter(
            ProgramSpecificOutcome.subject_id == subject_id
        ).order_by(ProgramSpecificOutcome.pso_code).all()

    return {
        "subject": subject,
        "cos": cos,
        "pos": pos,
        "psos": psos,
    }


def run_mapping_generation(
    db: Session,
    subject_id: int,
    method: str = "hybrid",
    context: Optional[str] = None,
) -> List[Dict]:
    """
    Run the AI mapping pipeline for a subject.

    1. Loads COs, POs, PSOs from database
    2. Runs the AI pipeline
    3. Saves results to database
    4. Returns the mapping results

    Returns list of mapping dicts.
    """
    data = get_subject_data(db, subject_id)

    if not data["cos"]:
        raise ValueError("No Course Outcomes found for this subject")
    if not data["pos"] and not data["psos"]:
        raise ValueError("No Program Outcomes or PSOs found for this subject")

    # Prepare inputs
    co_codes = [co.co_code for co in data["cos"]]
    co_texts = [co.description for co in data["cos"]]

    def outcome_code(outcome):
        return getattr(outcome, "outcome_code", None) or getattr(outcome, "po_code", None) or outcome.pso_code

    po_pso_codes = [outcome_code(po) for po in data["pos"]] + [outcome_code(pso) for pso in data["psos"]]
    po_pso_texts = [po.description for po in data["pos"]] + [pso.description for pso in data["psos"]]
    po_pso_types = ["PO"] * len(data["pos"]) + ["PSO"] * len(data["psos"])

    # Build ID lookup
    po_id_map = {outcome_code(po): po.id for po in data["pos"]}
    pso_id_map = {outcome_code(pso): pso.id for pso in data["psos"]}
    co_id_map = {co.co_code: co.id for co in data["cos"]}

    # Run AI pipeline
    logger.info(f"Generating mappings for subject {subject_id} using {method}")
    feedback_examples = _feedback_examples(db, data["subject"].framework_id, subject_id)
    feedback_context = _feedback_context(feedback_examples)
    combined_context = "\n\n".join(part for part in [context, feedback_context] if part)
    results, validation, metadata = generate_mappings(
        method=method,
        co_codes=co_codes,
        co_texts=co_texts,
        po_pso_codes=po_pso_codes,
        po_pso_texts=po_pso_texts,
        po_pso_types=po_pso_types,
        context=combined_context or None,
    )
    results = _apply_feedback_priors(results, co_codes, co_texts, feedback_examples)

    # Clear existing AI mappings for this subject+method
    db.query(AIMappingResult).filter(
        AIMappingResult.subject_id == subject_id,
        AIMappingResult.method == method,
    ).delete()

    # Save results to database
    saved_results = []
    for result in results:
        po_pso_type = "PSO" if result.po_pso_code.startswith("PSO") else "PO"

        if po_pso_type == "PO":
            po_pso_id = po_id_map.get(result.po_pso_code, 0)
        else:
            po_pso_id = pso_id_map.get(result.po_pso_code, 0)

        db_mapping = AIMappingResult(
            subject_id=subject_id,
            co_id=co_id_map.get(result.co_code, 0),
            co_code=result.co_code,
            po_pso_id=po_pso_id,
            po_pso_code=result.po_pso_code,
            po_pso_type=po_pso_type,
            mapping_level=result.mapping_level,
            confidence=result.confidence,
            similarity_score=result.similarity_score,
            reason=result.reason,
            evidence=json.dumps(result.evidence),
            method=method,
            faculty_decision=FacultyDecision.PENDING,
        )
        db.add(db_mapping)
        saved_results.append(db_mapping)

    db.commit()

    # Refresh to get IDs
    for r in saved_results:
        db.refresh(r)

    logger.info(
        f"Saved {len(saved_results)} mappings. "
        f"Validation: {validation.error_count} errors, {validation.warning_count} warnings"
    )

    return [_mapping_to_dict(r) for r in saved_results]


def get_mappings_for_subject(
    db: Session,
    subject_id: int,
    method: Optional[str] = None,
) -> List[Dict]:
    """Get all AI mapping results for a subject."""
    query = db.query(AIMappingResult).filter(
        AIMappingResult.subject_id == subject_id
    )
    if method:
        query = query.filter(AIMappingResult.method == method)

    results = query.order_by(
        AIMappingResult.co_code,
        AIMappingResult.po_pso_code
    ).all()

    return [_mapping_to_dict(r) for r in results]


def review_mapping(
    db: Session,
    mapping_id: int,
    decision: str,
    final_level: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict:
    """Review a single mapping (accept/edit/reject)."""
    mapping = db.query(AIMappingResult).filter(
        AIMappingResult.id == mapping_id
    ).first()

    if not mapping:
        raise ValueError(f"Mapping {mapping_id} not found")

    mapping.faculty_decision = FacultyDecision(decision)
    mapping.reviewed_at = datetime.utcnow()

    if final_level is not None and final_level not in {0, 1, 2, 3}:
        raise ValueError("Mapping level must be between 0 and 3")
    if decision == "edited" and final_level is not None:
        mapping.final_mapping_level = final_level
    elif decision == "accepted":
        mapping.final_mapping_level = mapping.mapping_level
    elif decision == "rejected":
        mapping.final_mapping_level = 0

    if notes:
        mapping.faculty_notes = notes

    db.commit()
    db.refresh(mapping)

    return _mapping_to_dict(mapping)


def batch_review_mappings(
    db: Session,
    mapping_ids: List[int],
    decision: str,
) -> List[Dict]:
    """Batch review multiple mappings."""
    results = []
    for mid in mapping_ids:
        try:
            result = review_mapping(db, mid, decision)
            results.append(result)
        except ValueError:
            continue
    return results


def save_reference_mappings(
    db: Session,
    subject_id: int,
    mappings: Dict[Tuple[str, str], int],
    source_file: str = "",
) -> int:
    """Save reference/ground-truth mappings from Excel."""
    # Clear existing reference mappings
    db.query(ReferenceMappingEntry).filter(
        ReferenceMappingEntry.subject_id == subject_id
    ).delete()

    count = 0
    for (co_code, po_pso_code), level in mappings.items():
        po_pso_type = "PSO" if po_pso_code.startswith("PSO") else "PO"
        entry = ReferenceMappingEntry(
            subject_id=subject_id,
            co_code=co_code,
            po_pso_code=po_pso_code,
            po_pso_type=po_pso_type,
            mapping_level=level,
            source_file=source_file,
        )
        db.add(entry)
        count += 1

    db.commit()
    logger.info(f"Saved {count} reference mappings for subject {subject_id}")
    return count


def run_evaluation(
    db: Session,
    subject_id: int,
    method: Optional[str] = None,
) -> Dict:
    """
    Evaluate AI mappings against reference mappings.

    If method is None, evaluates all available methods.
    """
    # Load reference mappings
    ref_entries = db.query(ReferenceMappingEntry).filter(
        ReferenceMappingEntry.subject_id == subject_id
    ).all()

    if not ref_entries:
        raise ValueError("No reference mappings found for this subject")

    reference_mappings = {
        (e.co_code, e.po_pso_code): e.mapping_level for e in ref_entries
    }

    methods_to_eval = [method] if method else ["hybrid", "embedding_only", "llm_only"]
    all_reports = {}

    for m in methods_to_eval:
        ai_entries = db.query(AIMappingResult).filter(
            AIMappingResult.subject_id == subject_id,
            AIMappingResult.method == m,
        ).all()

        if not ai_entries:
            continue

        ai_mappings = {
            (e.co_code, e.po_pso_code): e.mapping_level for e in ai_entries
        }

        report = evaluate_mappings(ai_mappings, reference_mappings, method=m)
        all_reports[m] = report

        # Save to database
        db_eval = MappingEvaluation(
            subject_id=subject_id,
            method=m,
            accuracy=report.accuracy,
            precision_macro=report.precision_macro,
            recall_macro=report.recall_macro,
            f1_macro=report.f1_macro,
            agreement_percentage=report.agreement_percentage,
            per_co_accuracy=json.dumps(report.per_co_accuracy),
            per_po_accuracy=json.dumps(report.per_po_accuracy),
            confusion_matrix=json.dumps(
                report.confusion_mat.tolist() if report.confusion_mat is not None else []
            ),
            classification_report=report.class_report,
        )
        db.add(db_eval)

    db.commit()

    return {
        m: r.to_dict() for m, r in all_reports.items()
    }


def get_evaluation_results(
    db: Session,
    subject_id: int,
) -> List[Dict]:
    """Get stored evaluation results for a subject."""
    results = db.query(MappingEvaluation).filter(
        MappingEvaluation.subject_id == subject_id
    ).order_by(MappingEvaluation.created_at.desc()).all()

    output = []
    for r in results:
        output.append({
            "id": r.id,
            "subject_id": r.subject_id,
            "method": r.method,
            "accuracy": r.accuracy,
            "precision_macro": r.precision_macro,
            "recall_macro": r.recall_macro,
            "f1_macro": r.f1_macro,
            "agreement_percentage": r.agreement_percentage,
            "per_co_accuracy": json.loads(r.per_co_accuracy) if r.per_co_accuracy else {},
            "per_po_accuracy": json.loads(r.per_po_accuracy) if r.per_po_accuracy else {},
            "confusion_matrix": json.loads(r.confusion_matrix) if r.confusion_matrix else [],
            "classification_report": r.classification_report,
        })

    return output


def _mapping_to_dict(m: AIMappingResult) -> Dict:
    """Convert an AIMappingResult to a dict."""
    return {
        "id": m.id,
        "subject_id": m.subject_id,
        "co_code": m.co_code,
        "po_pso_code": m.po_pso_code,
        "po_pso_type": m.po_pso_type,
        "mapping_level": m.mapping_level,
        "confidence": m.confidence,
        "similarity_score": m.similarity_score,
        "reason": m.reason,
        "evidence": json.loads(m.evidence) if m.evidence else [],
        "method": m.method,
        "faculty_decision": m.faculty_decision.value if m.faculty_decision else "pending",
        "final_mapping_level": m.final_mapping_level,
        "faculty_notes": m.faculty_notes,
        "reviewed_at": m.reviewed_at.isoformat() if m.reviewed_at else None,
    }


def _feedback_examples(db: Session, framework_id: Optional[int], subject_id: int) -> List[Dict]:
    """Return teacher-reviewed examples from the same programme framework.

    They are intentionally stored with the mapping record, not as opaque model
    training data: faculty can audit every example that influenced a suggestion.
    """
    if framework_id:
        reviewed = db.query(AIMappingResult, CourseOutcome).join(
            CourseOutcome, CourseOutcome.id == AIMappingResult.co_id
        ).join(Subject, Subject.id == AIMappingResult.subject_id).filter(
            Subject.framework_id == framework_id,
            AIMappingResult.faculty_decision.in_([FacultyDecision.EDITED, FacultyDecision.ACCEPTED]),
        ).order_by(AIMappingResult.reviewed_at.desc()).limit(60).all()
    else:
        reviewed = db.query(AIMappingResult, CourseOutcome).join(
            CourseOutcome, CourseOutcome.id == AIMappingResult.co_id
        ).filter(
            AIMappingResult.subject_id == subject_id,
            AIMappingResult.faculty_decision.in_([FacultyDecision.EDITED, FacultyDecision.ACCEPTED]),
        ).order_by(AIMappingResult.reviewed_at.desc()).limit(60).all()
    return [{
        "co_text": co.description,
        "outcome_code": mapping.po_pso_code,
        "level": mapping.final_mapping_level if mapping.final_mapping_level is not None else mapping.mapping_level,
        "notes": mapping.faculty_notes or "",
    } for mapping, co in reviewed]


def _feedback_context(examples: List[Dict]) -> str:
    if not examples:
        return ""
    lines = ["## Verified faculty feedback to use as calibration examples"]
    for item in examples[:12]:
        lines.append(f'- For {item["outcome_code"]}, teachers assigned level {item["level"]} to CO: "{item["co_text"]}". {item["notes"]}')
    return "\n".join(lines)


def _apply_feedback_priors(results, co_codes: List[str], co_texts: List[str], examples: List[Dict]):
    """Calibrate predictions when an earlier, similar CO was reviewed.

    This is lightweight continual learning: it only acts on a strong lexical
    match, preserves the explanation trail, and never hides the AI's original
    judgement. The prompt receives the same examples for semantic reasoning.
    """
    text_by_code = dict(zip(co_codes, co_texts))
    for result in results:
        current_tokens = set(text_by_code.get(result.co_code, "").lower().split())
        best = None
        for example in examples:
            if example["outcome_code"] != result.po_pso_code:
                continue
            prior_tokens = set(example["co_text"].lower().split())
            similarity = len(current_tokens & prior_tokens) / max(1, len(current_tokens | prior_tokens))
            if best is None or similarity > best[0]:
                best = (similarity, example)
        if best and best[0] >= 0.42:
            similarity, example = best
            result.mapping_level = example["level"]
            result.confidence = max(result.confidence, min(0.95, 0.55 + similarity / 2))
            result.reason = (
                f"{result.reason} Calibrated with similar verified faculty feedback "
                f"for {result.po_pso_code} (text overlap {similarity:.0%})."
            )
            result.evidence = list(result.evidence) + ["verified faculty feedback"]
    return results
