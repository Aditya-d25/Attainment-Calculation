"""
PDF Upload and Syllabus Extraction Router.
"""

import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from database import SessionLocal
from models import OutcomeFramework, FrameworkOutcome, Subject, CourseOutcome
from services.pdf_parser import parse_pdf_syllabus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pdf", tags=["PDF Processing"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload")
async def upload_syllabus_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a single syllabus PDF containing POs and COs for multiple courses.
    Automatically extracts:
    - Shared Program Outcomes (POs / PSOs)
    - Courses and their Course Outcomes (COs)
    Saves them into the database framework & subjects structure.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are supported")

    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    file_path = os.path.join(uploads_dir, unique_filename)

    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"Failed to save uploaded PDF: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    try:
        parsed_data = parse_pdf_syllabus(file_path)
    except Exception as e:
        logger.error(f"Error parsing PDF syllabus: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to extract syllabus data from PDF: {str(e)}")

    if not parsed_data["program_outcomes"] and not parsed_data["courses"]:
        raise HTTPException(
            status_code=400,
            detail="Could not detect any POs or Course Outcomes in the uploaded PDF. Please verify the PDF file format."
        )

    framework_name = parsed_data["framework_name"]
    department = parsed_data["department"]

    # 1. Create or retrieve OutcomeFramework
    framework = db.query(OutcomeFramework).filter(OutcomeFramework.name == framework_name).first()
    if not framework:
        framework = OutcomeFramework(
            name=framework_name,
            department=department,
            description=f"Auto-extracted from {file.filename} (Academic Year: {parsed_data['academic_year']})"
        )
        db.add(framework)
        db.commit()
        db.refresh(framework)

    # 2. Update Framework Outcomes (POs and PSOs)
    if parsed_data["program_outcomes"]:
        db.query(FrameworkOutcome).filter(FrameworkOutcome.framework_id == framework.id).delete()
        new_outcomes = []
        for po in parsed_data["program_outcomes"]:
            fo = FrameworkOutcome(
                framework_id=framework.id,
                outcome_code=po["outcome_code"],
                outcome_type=po["outcome_type"],
                description=po["description"]
            )
            new_outcomes.append(fo)
        db.add_all(new_outcomes)
        db.commit()

        # Invalidate cached framework vectors so they are re-embedded
        try:
            from ai.vector_store import invalidate_framework
            invalidate_framework(framework.id)
        except Exception:
            pass  # Vector store is optional; don't block the upload

    # 3. Process Courses & COs
    saved_courses = []
    for c_data in parsed_data["courses"]:
        code = c_data["course_code"]
        name = c_data["course_name"]

        subject = db.query(Subject).filter(Subject.course_code == code).first()
        if not subject:
            subject = Subject(
                course_code=code,
                course_name=name,
                framework_id=framework.id,
                department=department,
                academic_year=parsed_data["academic_year"]
            )
            db.add(subject)
            db.commit()
            db.refresh(subject)
        else:
            subject.course_name = name
            subject.framework_id = framework.id
            db.commit()

        # Update Course Outcomes for this subject
        if c_data["course_outcomes"]:
            from models import AIMappingResult
            db.query(AIMappingResult).filter(AIMappingResult.subject_id == subject.id).delete()
            db.query(CourseOutcome).filter(CourseOutcome.subject_id == subject.id).delete()
            cos_to_add = []
            for co in c_data["course_outcomes"]:
                cos_to_add.append(CourseOutcome(
                    subject_id=subject.id,
                    co_code=co["co_code"],
                    description=co["description"]
                ))
            db.add_all(cos_to_add)
            db.commit()

            # Invalidate cached CO vectors for this subject
            try:
                from ai.vector_store import invalidate_subject
                invalidate_subject(subject.id)
            except Exception:
                pass  # Vector store is optional

        saved_courses.append({
            "id": subject.id,
            "course_code": subject.course_code,
            "course_name": subject.course_name,
            "co_count": len(c_data["course_outcomes"])
        })

    return {
        "status": "success",
        "message": f"Successfully extracted syllabus data from '{file.filename}'",
        "framework": {
            "id": framework.id,
            "name": framework.name,
            "po_count": len(parsed_data["program_outcomes"])
        },
        "courses": saved_courses
    }
