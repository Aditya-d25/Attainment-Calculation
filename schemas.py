from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
from datetime import datetime


# -------------------------
# Enums
# -------------------------

class FacultyDecisionEnum(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class MappingMethodEnum(str, Enum):
    HYBRID = "hybrid"
    EMBEDDING_ONLY = "embedding_only"
    LLM_ONLY = "llm_only"


# -------------------------
# Subject Schemas
# -------------------------

class SubjectCreate(BaseModel):
    course_code: str
    course_name: str
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    department: Optional[str] = None
    theory_enabled: bool = True
    description: Optional[str] = None


class SubjectResponse(BaseModel):
    id: int
    course_code: str
    course_name: str
    semester: Optional[str]
    academic_year: Optional[str]
    department: Optional[str]
    theory_enabled: bool
    description: Optional[str]

    class Config:
        from_attributes = True


# -------------------------
# Course Outcome Schemas
# -------------------------

class CourseOutcomeCreate(BaseModel):
    co_code: str
    description: str
    univ_attainment: Optional[float] = 0.0
    internal_attainment: Optional[float] = 0.0


class CourseOutcomeUpdate(BaseModel):
    univ_attainment: Optional[float] = None
    internal_attainment: Optional[float] = None
    description: Optional[str] = None


class CourseOutcomeResponse(BaseModel):
    id: int
    subject_id: int
    co_code: str
    description: str
    univ_attainment: Optional[float] = 0.0
    internal_attainment: Optional[float] = 0.0

    class Config:
        from_attributes = True


# -------------------------
# Program Outcome Schemas
# -------------------------

class ProgramOutcomeCreate(BaseModel):
    po_code: str
    description: str


class ProgramOutcomeResponse(BaseModel):
    id: int
    subject_id: int
    po_code: str
    description: str

    class Config:
        from_attributes = True


# -------------------------
# PSO Schemas
# -------------------------

class PSOCreate(BaseModel):
    pso_code: str
    description: str


class PSOResponse(BaseModel):
    id: int
    subject_id: int
    pso_code: str
    description: str

    class Config:
        from_attributes = True


# -------------------------
# Mapping Schemas
# -------------------------

class MappingGenerateRequest(BaseModel):
    subject_id: int
    method: MappingMethodEnum = MappingMethodEnum.HYBRID
    context: Optional[str] = None


class MappingDirectRequest(BaseModel):
    """Generate mappings without saving to database first."""
    course_outcomes: List[CourseOutcomeCreate]
    program_outcomes: List[ProgramOutcomeCreate]
    program_specific_outcomes: Optional[List[PSOCreate]] = []
    method: MappingMethodEnum = MappingMethodEnum.HYBRID
    context: Optional[str] = None


class MappingResultResponse(BaseModel):
    id: int
    subject_id: int
    co_code: str
    po_pso_code: str
    po_pso_type: str
    mapping_level: int
    confidence: float
    similarity_score: float
    reason: Optional[str]
    evidence: Optional[str]
    method: str
    faculty_decision: str
    final_mapping_level: Optional[int]
    faculty_notes: Optional[str]
    reviewed_at: Optional[datetime]

    class Config:
        from_attributes = True


class MappingMatrixCell(BaseModel):
    co_code: str
    po_pso_code: str
    po_pso_type: str
    mapping_level: int
    confidence: float
    similarity_score: float
    reason: Optional[str]
    evidence: Optional[str]
    faculty_decision: str
    final_mapping_level: Optional[int]
    mapping_id: Optional[int] = None


class MappingMatrixResponse(BaseModel):
    subject_id: int
    co_codes: List[str]
    po_codes: List[str]
    pso_codes: List[str]
    matrix: List[MappingMatrixCell]
    method: str


# -------------------------
# Review Schemas
# -------------------------

class ReviewAction(BaseModel):
    faculty_decision: FacultyDecisionEnum
    final_mapping_level: Optional[int] = None
    faculty_notes: Optional[str] = None


class BatchReviewAction(BaseModel):
    mapping_ids: List[int]
    faculty_decision: FacultyDecisionEnum


# -------------------------
# Evaluation Schemas
# -------------------------

class EvaluationRequest(BaseModel):
    subject_id: int
    method: Optional[MappingMethodEnum] = None


class EvaluationResultResponse(BaseModel):
    id: int
    subject_id: int
    method: str
    accuracy: Optional[float]
    precision_macro: Optional[float]
    recall_macro: Optional[float]
    f1_macro: Optional[float]
    agreement_percentage: Optional[float]
    per_co_accuracy: Optional[str]
    per_po_accuracy: Optional[str]
    confusion_matrix: Optional[str]
    classification_report: Optional[str]

    class Config:
        from_attributes = True


class ComparisonResultResponse(BaseModel):
    evaluations: List[EvaluationResultResponse]


# -------------------------
# Config Schema
# -------------------------

class ConfigResponse(BaseModel):
    llm_provider: str
    llm_model: str
    embedding_model: str
    mock_mode: bool
