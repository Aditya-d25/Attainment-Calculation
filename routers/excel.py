"""
Excel upload and export API routes.
"""

import os
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Document, Subject, CourseOutcome, ProgramOutcome, ProgramSpecificOutcome, FrameworkOutcome
from services.excel_parser import parse_reference_excel
from services.excel_exporter import export_mapping_report
from services.mapping_service import (
    save_reference_mappings,
    get_mappings_for_subject,
    get_evaluation_results,
)

router = APIRouter(prefix="/api/excel", tags=["Excel"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload-reference/{subject_id}")
async def upload_reference_excel(
    subject_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a faculty reference Excel workbook.

    Extracts CO-PO mappings and optionally CO descriptions.
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    # Save file
    file_id = str(uuid.uuid4())[:8]
    filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Parse the Excel file
    parse_result = parse_reference_excel(file_path)

    if parse_result.errors:
        return {
            "status": "error",
            "errors": parse_result.errors,
            "data": parse_result.to_dict(),
        }

    # Save reference mappings to database
    count = save_reference_mappings(
        db=db,
        subject_id=subject_id,
        mappings=parse_result.mappings,
        source_file=filename,
    )

    # Save document record
    doc = Document(
        subject_id=subject_id,
        filename=filename,
        file_path=file_path,
        doc_type="reference_mapping",
    )
    db.add(doc)
    db.commit()

    return {
        "status": "success",
        "filename": filename,
        "sheet_name": parse_result.sheet_name,
        "co_codes": parse_result.co_codes,
        "po_codes": parse_result.po_codes,
        "pso_codes": parse_result.pso_codes,
        "co_descriptions": parse_result.co_descriptions,
        "mappings_count": count,
        "data": parse_result.to_dict(),
    }


@router.get("/export/{subject_id}")
def export_mapping_excel(
    subject_id: int,
    db: Session = Depends(get_db),
):
    """Export the mapping results as an Excel report."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Get mappings
    mappings_list = get_mappings_for_subject(db, subject_id)
    if not mappings_list:
        raise HTTPException(status_code=400, detail="No mappings found for this subject")

    # Use the stream-wide catalogue for framework-backed courses.
    if subject.framework_id:
        rows = db.query(FrameworkOutcome).filter(FrameworkOutcome.framework_id == subject.framework_id).all()
        po_codes = [row.outcome_code for row in rows if row.outcome_type == "PO"]
        pso_codes = [row.outcome_code for row in rows if row.outcome_type == "PSO"]
    else:
        pos = db.query(ProgramOutcome).filter(ProgramOutcome.subject_id == subject_id).order_by(ProgramOutcome.po_code).all()
        psos = db.query(ProgramSpecificOutcome).filter(ProgramSpecificOutcome.subject_id == subject_id).order_by(ProgramSpecificOutcome.pso_code).all()
        po_codes = [po.po_code for po in pos]
        pso_codes = [pso.pso_code for pso in psos]
    cos = db.query(CourseOutcome).filter(
        CourseOutcome.subject_id == subject_id
    ).order_by(CourseOutcome.co_code).all()

    co_codes = [co.co_code for co in cos]

    # Convert to export format
    ai_mappings = {}
    for m in mappings_list:
        key = (m["co_code"], m["po_pso_code"])
        ai_mappings[key] = {
            "level": m["mapping_level"],
            "confidence": m["confidence"],
            "similarity": m["similarity_score"],
            "reason": m["reason"],
            "faculty_decision": m["faculty_decision"],
            "final_level": m.get("final_mapping_level", m["mapping_level"]),
            "faculty_notes": m.get("faculty_notes", ""),
        }

    # Get reference mappings if available
    from models import ReferenceMappingEntry
    ref_entries = db.query(ReferenceMappingEntry).filter(
        ReferenceMappingEntry.subject_id == subject_id
    ).all()
    reference_mappings = None
    if ref_entries:
        reference_mappings = {
            (e.co_code, e.po_pso_code): e.mapping_level for e in ref_entries
        }

    # Get evaluation results
    eval_results = get_evaluation_results(db, subject_id)
    evaluation = eval_results[0] if eval_results else None

    # Generate the file
    export_filename = f"mapping_report_{subject.course_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    export_path = os.path.join(UPLOAD_DIR, export_filename)

    export_mapping_report(
        file_path=export_path,
        subject_name=f"{subject.course_code} - {subject.course_name}",
        co_codes=co_codes,
        po_codes=po_codes,
        pso_codes=pso_codes,
        ai_mappings=ai_mappings,
        reference_mappings=reference_mappings,
        evaluation=evaluation,
    )

    return FileResponse(
        path=export_path,
        filename=export_filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
