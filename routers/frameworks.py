"""Programme-level PO/PSO framework API.

Teachers create a framework once per stream (for example, CSE 2026) and all
courses attached to it use exactly the same outcome definitions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
from models import OutcomeFramework, FrameworkOutcome, Subject
from schemas import (
    OutcomeFrameworkCreate, OutcomeFrameworkResponse,
    FrameworkOutcomeCreate, FrameworkOutcomeResponse,
)

router = APIRouter(prefix="/api/frameworks", tags=["Programme frameworks"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("", response_model=List[OutcomeFrameworkResponse])
def list_frameworks(db: Session = Depends(get_db)):
    return db.query(OutcomeFramework).order_by(OutcomeFramework.name).all()


@router.post("", response_model=OutcomeFrameworkResponse)
def create_framework(data: OutcomeFrameworkCreate, db: Session = Depends(get_db)):
    if db.query(OutcomeFramework).filter(OutcomeFramework.name == data.name).first():
        raise HTTPException(status_code=400, detail="A framework with this name already exists")
    framework = OutcomeFramework(**data.model_dump())
    db.add(framework)
    db.commit()
    db.refresh(framework)
    return framework


@router.get("/{framework_id}/outcomes", response_model=List[FrameworkOutcomeResponse])
def list_outcomes(framework_id: int, db: Session = Depends(get_db)):
    return db.query(FrameworkOutcome).filter(
        FrameworkOutcome.framework_id == framework_id
    ).order_by(FrameworkOutcome.outcome_type, FrameworkOutcome.outcome_code).all()


@router.post("/{framework_id}/outcomes/item", response_model=FrameworkOutcomeResponse)
def add_outcome_item(
    framework_id: int,
    item: FrameworkOutcomeCreate,
    db: Session = Depends(get_db),
):
    if not db.query(OutcomeFramework).filter(OutcomeFramework.id == framework_id).first():
        raise HTTPException(status_code=404, detail="Programme framework not found")
    code = item.outcome_code.strip().upper()
    otype = item.outcome_type.strip().upper()
    if otype not in {"PO", "PSO"}:
        raise HTTPException(status_code=400, detail="Outcome type must be PO or PSO")
    existing = db.query(FrameworkOutcome).filter(
        FrameworkOutcome.framework_id == framework_id,
        FrameworkOutcome.outcome_code == code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Outcome {code} already exists in this framework")
    row = FrameworkOutcome(
        framework_id=framework_id,
        outcome_code=code,
        outcome_type=otype,
        description=item.description.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{framework_id}/outcomes/item/{outcome_id}", response_model=FrameworkOutcomeResponse)
def update_outcome_item(
    framework_id: int,
    outcome_id: int,
    item: FrameworkOutcomeCreate,
    db: Session = Depends(get_db),
):
    row = db.query(FrameworkOutcome).filter(
        FrameworkOutcome.id == outcome_id,
        FrameworkOutcome.framework_id == framework_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Framework outcome not found")

    code = item.outcome_code.strip().upper()
    otype = item.outcome_type.strip().upper()
    if otype not in {"PO", "PSO"}:
        raise HTTPException(status_code=400, detail="Outcome type must be PO or PSO")

    # Check code collision if code changed
    if code != row.outcome_code:
        conflict = db.query(FrameworkOutcome).filter(
            FrameworkOutcome.framework_id == framework_id,
            FrameworkOutcome.outcome_code == code,
            FrameworkOutcome.id != outcome_id
        ).first()
        if conflict:
            raise HTTPException(status_code=400, detail=f"Outcome code {code} already exists")

    row.outcome_code = code
    row.outcome_type = otype
    row.description = item.description.strip()
    db.commit()
    db.refresh(row)

    try:
        from ai.vector_store import invalidate_framework
        invalidate_framework(framework_id)
    except Exception:
        pass

    return row


@router.delete("/{framework_id}/outcomes/item/{outcome_id}")
def delete_outcome_item(
    framework_id: int,
    outcome_id: int,
    db: Session = Depends(get_db),
):
    row = db.query(FrameworkOutcome).filter(
        FrameworkOutcome.id == outcome_id,
        FrameworkOutcome.framework_id == framework_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Framework outcome not found")
    db.delete(row)
    db.commit()

    try:
        from ai.vector_store import invalidate_framework
        invalidate_framework(framework_id)
    except Exception:
        pass

    return {"status": "success", "message": "Framework outcome deleted"}


@router.put("/{framework_id}/outcomes", response_model=List[FrameworkOutcomeResponse])
def replace_outcomes(
    framework_id: int,
    outcomes: List[FrameworkOutcomeCreate],
    db: Session = Depends(get_db),
):
    if not db.query(OutcomeFramework).filter(OutcomeFramework.id == framework_id).first():
        raise HTTPException(status_code=404, detail="Programme framework not found")
    codes = [item.outcome_code.strip().upper() for item in outcomes]
    if len(codes) != len(set(codes)):
        raise HTTPException(status_code=400, detail="Each outcome code must be unique")
    if any(item.outcome_type.upper() not in {"PO", "PSO"} for item in outcomes):
        raise HTTPException(status_code=400, detail="Outcome type must be PO or PSO")
    db.query(FrameworkOutcome).filter(FrameworkOutcome.framework_id == framework_id).delete()
    rows = [FrameworkOutcome(
        framework_id=framework_id,
        outcome_code=item.outcome_code.strip().upper(),
        outcome_type=item.outcome_type.strip().upper(),
        description=item.description.strip(),
    ) for item in outcomes]
    db.add_all(rows)
    db.commit()

    try:
        from ai.vector_store import invalidate_framework
        invalidate_framework(framework_id)
    except Exception:
        pass

    return db.query(FrameworkOutcome).filter(
        FrameworkOutcome.framework_id == framework_id
    ).order_by(FrameworkOutcome.outcome_type, FrameworkOutcome.outcome_code).all()


@router.put("/{framework_id}/subjects/{subject_id}")
def attach_subject(framework_id: int, subject_id: int, db: Session = Depends(get_db)):
    if not db.query(OutcomeFramework).filter(OutcomeFramework.id == framework_id).first():
        raise HTTPException(status_code=404, detail="Programme framework not found")
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    subject.framework_id = framework_id
    db.commit()
    return {"status": "success", "framework_id": framework_id, "subject_id": subject_id}
