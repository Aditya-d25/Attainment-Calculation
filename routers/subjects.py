"""
Subject, Course Outcome, Program Outcome, and PSO API routes.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

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
def list_subjects(year: Optional[str] = None, department: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Subject)
    if year and year != "All":
        query = query.filter(Subject.year == year)
    if department and department != "All":
        query = query.filter(Subject.department == department)
    return query.order_by(Subject.course_name).all()


@router.get("/meta/hierarchy")
def get_hierarchy(db: Session = Depends(get_db)):
    """Return distinct years, departments, and subjects tree for cascading dropdowns."""
    subjects = db.query(Subject).order_by(Subject.course_name).all()
    preferred_order = ["FE", "SE", "TE", "BE"]
    all_years = list({s.year for s in subjects if s.year})
    years = sorted(all_years, key=lambda y: preferred_order.index(y) if y in preferred_order else 99)
    departments = sorted(list({s.department for s in subjects if s.department}))
    
    tree = {}
    for y in years:
        tree[y] = {}
        for s in subjects:
            if s.year == y:
                d = s.department or "General"
                if d not in tree[y]:
                    tree[y][d] = []
                tree[y][d].append({
                    "id": s.id,
                    "course_code": s.course_code,
                    "course_name": s.course_name,
                    "year": s.year,
                    "department": s.department,
                    "co_count": s.co_count,
                    "framework_id": s.framework_id,
                })
                
    return {
        "years": years,
        "departments": departments,
        "tree": tree,
        "total_subjects": len(subjects),
    }


@router.get("/{subject_id}/outcomes-status")
def get_subject_outcomes_status(subject_id: int, db: Session = Depends(get_db)):
    """Fetch COs and POs directly from DB for a subject, with status flag."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    cos = db.query(CourseOutcome).filter(CourseOutcome.subject_id == subject.id).order_by(CourseOutcome.co_code).all()
    
    pos = []
    framework_name = None
    if subject.framework_id:
        framework = db.query(OutcomeFramework).filter(OutcomeFramework.id == subject.framework_id).first()
        if framework:
            framework_name = framework.name
            pos = db.query(FrameworkOutcome).filter(FrameworkOutcome.framework_id == framework.id).order_by(FrameworkOutcome.outcome_code).all()
    
    # If no framework outcomes, check direct subject POs
    if not pos:
        subject_pos = db.query(ProgramOutcome).filter(ProgramOutcome.subject_id == subject.id).all()
        subject_psos = db.query(ProgramSpecificOutcome).filter(ProgramSpecificOutcome.subject_id == subject.id).all()
        for p in subject_pos:
            pos.append({"outcome_code": p.po_code, "outcome_type": "PO", "description": p.description})
        for p in subject_psos:
            pos.append({"outcome_code": p.pso_code, "outcome_type": "PSO", "description": p.description})
    else:
        pos = [
            {"id": p.id, "outcome_code": p.outcome_code, "outcome_type": p.outcome_type, "description": p.description}
            for p in pos
        ]

    co_list = [
        {
            "id": c.id,
            "co_code": c.co_code,
            "description": c.description,
            "univ_attainment": c.univ_attainment,
            "internal_attainment": c.internal_attainment,
        }
        for c in cos
    ]

    has_cos = len(co_list) > 0

    return {
        "subject_id": subject.id,
        "course_code": subject.course_code,
        "course_name": subject.course_name,
        "year": subject.year,
        "department": subject.department,
        "framework_id": subject.framework_id,
        "framework_name": framework_name,
        "has_outcomes": has_cos,
        "co_count": len(co_list),
        "po_count": len(pos),
        "cos": co_list,
        "pos": pos,
    }


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

    # Invalidate cached vectors for this subject
    try:
        from ai.vector_store import invalidate_subject
        invalidate_subject(subject_id)
    except Exception:
        pass

    return {"message": "Subject deleted"}


# -------------------------
# Course Outcome CRUD
# -------------------------

@router.post("/{subject_id}/cos", response_model=CourseOutcomeResponse)
def create_co(subject_id: int, data: CourseOutcomeCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    co = CourseOutcome(subject_id=subject_id, **payload)
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

    old_code = co.co_code
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

    # Invalidate vector cache if code or description changed
    if data.description is not None or data.co_code is not None:
        try:
            from ai.vector_store import invalidate_co
            invalidate_co(subject_id, old_code)
            if co.co_code != old_code:
                invalidate_co(subject_id, co.co_code)
        except Exception:
            pass

    return co


@router.delete("/{subject_id}/cos/{co_id}")
def delete_co(subject_id: int, co_id: int, db: Session = Depends(get_db)):
    co = db.query(CourseOutcome).filter(
        CourseOutcome.id == co_id,
        CourseOutcome.subject_id == subject_id,
    ).first()
    if not co:
        raise HTTPException(status_code=404, detail="CO not found")
    old_code = co.co_code
    db.query(AIMappingResult).filter(AIMappingResult.co_id == co_id).delete()
    db.delete(co)
    db.commit()

    try:
        from ai.vector_store import invalidate_co
        invalidate_co(subject_id, old_code)
    except Exception:
        pass

    return {"message": "CO deleted"}


# -------------------------
# Program Outcome CRUD
# -------------------------

@router.post("/{subject_id}/pos", response_model=ProgramOutcomeResponse)
def create_po(subject_id: int, data: ProgramOutcomeCreate, db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    po = ProgramOutcome(subject_id=subject_id, **payload)
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
        payload = item.model_dump() if hasattr(item, "model_dump") else item.dict()
        po = ProgramOutcome(subject_id=subject_id, **payload)
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

    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    pso = ProgramSpecificOutcome(subject_id=subject_id, **payload)
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
        payload = item.model_dump() if hasattr(item, "model_dump") else item.dict()
        pso = ProgramSpecificOutcome(subject_id=subject_id, **payload)
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
