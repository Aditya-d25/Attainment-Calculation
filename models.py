from sqlalchemy import (
    Column, Integer, String, Boolean, Float, Text,
    ForeignKey, DateTime, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String(50), unique=True, nullable=False)
    course_name = Column(String(200), nullable=False)
    semester = Column(String(50))
    academic_year = Column(String(50))
    department = Column(String(100))
    theory_enabled = Column(Boolean, default=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    course_outcomes = relationship("CourseOutcome", back_populates="subject", cascade="all, delete-orphan")
    program_outcomes = relationship("ProgramOutcome", back_populates="subject", cascade="all, delete-orphan")
    program_specific_outcomes = relationship("ProgramSpecificOutcome", back_populates="subject", cascade="all, delete-orphan")


class CourseOutcome(Base):
    __tablename__ = "course_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    co_code = Column(String(20), nullable=False)
    description = Column(String(1000), nullable=False)
    univ_attainment = Column(Float, nullable=True, default=0.0)
    internal_attainment = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime, server_default=func.now())

    subject = relationship("Subject", back_populates="course_outcomes")


class ProgramOutcome(Base):
    __tablename__ = "program_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    po_code = Column(String(20), nullable=False)
    description = Column(String(1000), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    subject = relationship("Subject", back_populates="program_outcomes")


class ProgramSpecificOutcome(Base):
    __tablename__ = "program_specific_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    pso_code = Column(String(20), nullable=False)
    description = Column(String(1000), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    subject = relationship("Subject", back_populates="program_specific_outcomes")


class FacultyDecision(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"


class MappingMethod(str, enum.Enum):
    HYBRID = "hybrid"
    EMBEDDING_ONLY = "embedding_only"
    LLM_ONLY = "llm_only"


class AIMappingResult(Base):
    __tablename__ = "ai_mapping_results"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    co_id = Column(Integer, ForeignKey("course_outcomes.id"), nullable=False)
    co_code = Column(String(20), nullable=False)
    po_pso_id = Column(Integer, nullable=False)
    po_pso_code = Column(String(20), nullable=False)
    po_pso_type = Column(String(10), nullable=False)  # "PO" or "PSO"

    # AI outputs
    mapping_level = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=0.0)
    similarity_score = Column(Float, nullable=False, default=0.0)
    reason = Column(Text, nullable=True)
    evidence = Column(Text, nullable=True)  # JSON array stored as text
    method = Column(String(20), nullable=False, default="hybrid")

    # Faculty review
    faculty_decision = Column(
        SQLEnum(FacultyDecision),
        default=FacultyDecision.PENDING,
        nullable=False
    )
    final_mapping_level = Column(Integer, nullable=True)
    faculty_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    course_outcome = relationship("CourseOutcome")


class ReferenceMappingEntry(Base):
    __tablename__ = "reference_mappings"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    co_code = Column(String(20), nullable=False)
    po_pso_code = Column(String(20), nullable=False)
    po_pso_type = Column(String(10), nullable=False)  # "PO" or "PSO"
    mapping_level = Column(Integer, nullable=False, default=0)
    source_file = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class MappingEvaluation(Base):
    __tablename__ = "mapping_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    method = Column(String(20), nullable=False, default="hybrid")

    # Overall metrics
    accuracy = Column(Float, nullable=True)
    precision_macro = Column(Float, nullable=True)
    recall_macro = Column(Float, nullable=True)
    f1_macro = Column(Float, nullable=True)
    agreement_percentage = Column(Float, nullable=True)

    # Detailed results stored as JSON text
    per_co_accuracy = Column(Text, nullable=True)
    per_po_accuracy = Column(Text, nullable=True)
    confusion_matrix = Column(Text, nullable=True)
    classification_report = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    doc_type = Column(String(50), nullable=False)  # "reference_mapping", "export"
    created_at = Column(DateTime, server_default=func.now())