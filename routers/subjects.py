"""
Subject, Course Outcome, Program Outcome, and PSO API routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import SessionLocal
from models import Subject, CourseOutcome, ProgramOutcome, ProgramSpecificOutcome, OutcomeFramework, FrameworkOutcome, AIMappingResult
from schemas import (
    SubjectCreate, SubjectResponse,
    CourseOutcomeCreate, CourseOutcomeUpdate, CourseOutcomeResponse,
    ProgramOutcomeCreate, ProgramOutcomeResponse,
    PSOCreate, PSOResponse,
)

router = APIRouter(prefix="/api/subjects", tags=["Subjects"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -------------------------
# Subject CRUD
# -------------------------

@router.post("", response_model=SubjectResponse)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db)):
    existing = db.query(Subject).filter(Subject.course_code == data.course_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Course code already exists")

    if data.framework_id and not db.query(OutcomeFramework).filter(OutcomeFramework.id == data.framework_id).first():
        raise HTTPException(status_code=400, detail="Programme framework not found")
    subject = Subject(**data.model_dump())
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


@router.get("", response_model=List[SubjectResponse])
def list_subjects(db: Session = Depends(get_db)):
    return db.query(Subject).all()


@router.get("/{subject_id}", response_model=SubjectResponse)
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return subject


@router.delete("/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    db.query(AIMappingResult).filter(AIMappingResult.subject_id == subject_id).delete()
    db.delete(subject)
    db.commit()
    return {"message": "Subject deleted"}


# -------------------------
# Course Outcome CRUD
# -------------------------

@router.post("/{subject_id}/cos", response_model=CourseOutcomeResponse)
def create_co(subject_id: int, data: CourseOutcomeCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    co = CourseOutcome(subject_id=subject_id, **data.dict())
    db.add(co)
    db.commit()
    db.refresh(co)
    return co


@router.get("/{subject_id}/cos", response_model=List[CourseOutcomeResponse])
def list_cos(subject_id: int, db: Session = Depends(get_db)):
    return db.query(CourseOutcome).filter(
        CourseOutcome.subject_id == subject_id
    ).order_by(CourseOutcome.co_code).all()


@router.put("/{subject_id}/cos/{co_id}", response_model=CourseOutcomeResponse)
def update_co(
    subject_id: int,
    co_id: int,
    data: CourseOutcomeUpdate,
    db: Session = Depends(get_db),
):
    co = db.query(CourseOutcome).filter(
        CourseOutcome.id == co_id,
        CourseOutcome.subject_id == subject_id,
    ).first()
    if not co:
        raise HTTPException(status_code=404, detail="CO not found")

    if data.co_code is not None:
        co.co_code = data.co_code.strip().upper()
    if data.univ_attainment is not None:
        co.univ_attainment = data.univ_attainment
    if data.internal_attainment is not None:
        co.internal_attainment = data.internal_attainment
    if data.description is not None:
        co.description = data.description

    db.commit()
    db.refresh(co)
    return co


@router.delete("/{subject_id}/cos/{co_id}")
def delete_co(subject_id: int, co_id: int, db: Session = Depends(get_db)):
    co = db.query(CourseOutcome).filter(
        CourseOutcome.id == co_id,
        CourseOutcome.subject_id == subject_id,
    ).first()
    if not co:
        raise HTTPException(status_code=404, detail="CO not found")
    db.query(AIMappingResult).filter(AIMappingResult.co_id == co_id).delete()
    db.delete(co)
    db.commit()
    return {"message": "CO deleted"}


# -------------------------
# Program Outcome CRUD
# -------------------------

@router.post("/{subject_id}/pos", response_model=ProgramOutcomeResponse)
def create_po(subject_id: int, data: ProgramOutcomeCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    po = ProgramOutcome(subject_id=subject_id, **data.dict())
    db.add(po)
    db.commit()
    db.refresh(po)
    return po


@router.post("/{subject_id}/pos/batch", response_model=List[ProgramOutcomeResponse])
def create_pos_batch(
    subject_id: int,
    data: List[ProgramOutcomeCreate],
    db: Session = Depends(get_db),
):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Clear existing POs
    db.query(ProgramOutcome).filter(ProgramOutcome.subject_id == subject_id).delete()

    pos = []
    for item in data:
        po = ProgramOutcome(subject_id=subject_id, **item.dict())
        db.add(po)
        pos.append(po)

    db.commit()
    for po in pos:
        db.refresh(po)
    return pos


@router.get("/{subject_id}/pos", response_model=List[ProgramOutcomeResponse])
def list_pos(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if subject and subject.framework_id:
        return [
            {"id": po.id, "subject_id": subject_id, "po_code": po.outcome_code, "description": po.description}
            for po in db.query(FrameworkOutcome).filter(
                FrameworkOutcome.framework_id == subject.framework_id,
                FrameworkOutcome.outcome_type == "PO",
            ).order_by(FrameworkOutcome.outcome_code).all()
        ]
    return db.query(ProgramOutcome).filter(
        ProgramOutcome.subject_id == subject_id
    ).order_by(ProgramOutcome.po_code).all()


# -------------------------
# PSO CRUD
# -------------------------

@router.post("/{subject_id}/psos", response_model=PSOResponse)
def create_pso(subject_id: int, data: PSOCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    pso = ProgramSpecificOutcome(subject_id=subject_id, **data.dict())
    db.add(pso)
    db.commit()
    db.refresh(pso)
    return pso


@router.post("/{subject_id}/psos/batch", response_model=List[PSOResponse])
def create_psos_batch(
    subject_id: int,
    data: List[PSOCreate],
    db: Session = Depends(get_db),
):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Clear existing PSOs
    db.query(ProgramSpecificOutcome).filter(
        ProgramSpecificOutcome.subject_id == subject_id
    ).delete()

    psos = []
    for item in data:
        pso = ProgramSpecificOutcome(subject_id=subject_id, **item.dict())
        db.add(pso)
        psos.append(pso)

    db.commit()
    for pso in psos:
        db.refresh(pso)
    return psos


@router.get("/{subject_id}/psos", response_model=List[PSOResponse])
def list_psos(subject_id: int, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if subject and subject.framework_id:
        return [
            {"id": pso.id, "subject_id": subject_id, "pso_code": pso.outcome_code, "description": pso.description}
            for pso in db.query(FrameworkOutcome).filter(
                FrameworkOutcome.framework_id == subject.framework_id,
                FrameworkOutcome.outcome_type == "PSO",
            ).order_by(FrameworkOutcome.outcome_code).all()
        ]
    return db.query(ProgramSpecificOutcome).filter(
        ProgramSpecificOutcome.subject_id == subject_id
    ).order_by(ProgramSpecificOutcome.pso_code).all()
