"""
AI Mapping API routes.

- Generate mappings
- Retrieve mappings
- Review (accept/edit/reject)
- Evaluate against reference
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from database import SessionLocal
from schemas import (
    MappingGenerateRequest,
    ReviewAction,
    BatchReviewAction,
    EvaluationRequest,
    ConfigResponse,
)
from services.mapping_service import (
    run_mapping_generation,
    get_mappings_for_subject,
    review_mapping,
    batch_review_mappings,
    run_evaluation,
    get_evaluation_results,
)

router = APIRouter(prefix="/api/mapping", tags=["Mapping"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/config/current")
def get_config():
    """Get current AI configuration (must precede the dynamic ID route)."""
    return ConfigResponse(
        llm_provider=os.getenv("LLM_PROVIDER", "groq"),
        llm_model=os.getenv("LLM_MODEL", "openai/gpt-oss-120b"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        mock_mode=os.getenv("MOCK_MODE", "false").lower() == "true",
    )


@router.post("/generate")
def generate_mapping(request: MappingGenerateRequest, db: Session = Depends(get_db)):
    """Generate AI CO-PO/PSO mappings for a subject."""
    try:
        results = run_mapping_generation(
            db=db,
            subject_id=request.subject_id,
            method=request.method.value,
            context=request.context,
        )
        return {
            "status": "success",
            "method": request.method.value,
            "count": len(results),
            "mappings": results,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mapping generation failed: {str(e)}")


@router.get("/{subject_id}")
def get_mappings(
    subject_id: int,
    method: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get all AI mapping results for a subject."""
    results = get_mappings_for_subject(db, subject_id, method)
    return {
        "subject_id": subject_id,
        "count": len(results),
        "mappings": results,
    }


@router.put("/{mapping_id}/review")
def review_single_mapping(
    mapping_id: int,
    action: ReviewAction,
    db: Session = Depends(get_db),
):
    """Review a single mapping (accept/edit/reject)."""
    try:
        result = review_mapping(
            db=db,
            mapping_id=mapping_id,
            decision=action.faculty_decision.value,
            final_level=action.final_mapping_level,
            notes=action.faculty_notes,
        )
        return {"status": "success", "mapping": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/batch-review")
def batch_review(action: BatchReviewAction, db: Session = Depends(get_db)):
    """Batch review multiple mappings."""
    results = batch_review_mappings(
        db=db,
        mapping_ids=action.mapping_ids,
        decision=action.faculty_decision.value,
    )
    return {
        "status": "success",
        "reviewed": len(results),
        "mappings": results,
    }


@router.post("/evaluate")
def evaluate_mapping(request: EvaluationRequest, db: Session = Depends(get_db)):
    """Evaluate AI mappings against reference/faculty mappings."""
    try:
        method = request.method.value if request.method else None
        results = run_evaluation(db, request.subject_id, method)
        return {
            "status": "success",
            "evaluations": results,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/evaluation/{subject_id}")
def get_evaluation(subject_id: int, db: Session = Depends(get_db)):
    """Get stored evaluation results."""
    results = get_evaluation_results(db, subject_id)
    return {
        "subject_id": subject_id,
        "evaluations": results,
    }
