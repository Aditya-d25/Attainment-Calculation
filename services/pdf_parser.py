"""
PDF Syllabus Parser — Automatically extracts POs, PSOs, Courses, and COs from University Syllabus PDFs.
Specifically optimized for SPPU, AICTE, and NEP-2020 engineering curriculum structures.
"""

import re
import logging
from typing import Dict, List, Optional
from pypdf import PdfReader

logger = logging.getLogger(__name__)


def clean_word_hyphenation(lines: List[str]) -> str:
    """
    Join lines while resolving hyphenated line breaks.
    e.g. 'applica-\n tion' -> 'application'
         'stake-\n holders' -> 'stakeholders'
    """
    text = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if text.endswith("-"):
            # Check if last token is an alphabetic word fragment
            parts = text.rsplit(None, 1)
            last_word = parts[-1] if parts else ""
            if len(last_word) > 1 and last_word[:-1].isalpha() and stripped[0].isalpha():
                text = text[:-1] + stripped
            else:
                text = text + " " + stripped
        else:
            text = (text + " " + stripped) if text else stripped
    return text.strip()


def extract_text_from_pdf(file_path: str) -> List[Dict[str, any]]:
    """Extract page-by-page text from PDF."""
    reader = PdfReader(file_path)
    pages_data = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        pages_data.append({
            "page_num": i + 1,
            "text": text
        })
    return pages_data


def parse_pdf_syllabus(file_path: str) -> Dict[str, any]:
    """
    Parses a syllabus PDF to extract:
    1. Framework Metadata (Title, Department, Academic Year)
    2. Program Outcomes (POs) & Program Specific Outcomes (PSOs)
    3. Courses and their respective Course Outcomes (COs)
    """
    pages_data = extract_text_from_pdf(file_path)
    full_text = "\n".join([p["text"] for p in pages_data])

    # 1. Extract Framework Metadata
    framework_name = _extract_framework_title(full_text, pages_data)
    department = _extract_department(full_text)
    academic_year = _extract_academic_year(full_text)

    # 2. Extract Program Outcomes (POs) & PSOs
    pos = _extract_program_outcomes(full_text, pages_data)

    # 3. Extract Courses & Course Outcomes (COs)
    courses = _extract_courses_and_cos(full_text, pages_data)

    logger.info(
        f"Parsed PDF syllabus: Framework='{framework_name}', "
        f"POs count={len(pos)}, Courses count={len(courses)}"
    )

    return {
        "framework_name": framework_name,
        "department": department,
        "academic_year": academic_year,
        "program_outcomes": pos,
        "courses": courses,
    }


def _extract_framework_title(full_text: str, pages_data: List[Dict]) -> str:
    """Extract syllabus title (e.g. Savitribai Phule Pune University - Electronics & Telecommunication Engineering (2024 Pattern))."""
    p1 = pages_data[0]["text"] if pages_data else ""
    lines = [line.strip() for line in p1.split("\n") if line.strip()]

    univ = ""
    branch = ""
    pattern = ""

    for line in lines[:25]:
        if re.match(r'^(PO\d+|CO\d+|PSO\d+|Course|Unit|Contents|Nomenclature)\b', line, re.IGNORECASE):
            continue
        if ("University" in line or "Institute" in line) and not univ:
            univ = re.sub(r",\s*Pune.*", "", line).strip()
        elif any(kw in line.lower() for kw in ["engineering", "technology"]) and not ("faculty" in line.lower() or "second year" in line.lower()) and not branch:
            branch = line.strip()
        elif ("Pattern" in line or "NEP" in line) and not pattern:
            pat_match = re.search(r'(\d{4}\s*Pattern|\bNEP[-\s]*2020\b)', line, re.IGNORECASE)
            if pat_match:
                pattern = pat_match.group(0).strip()
            else:
                pattern = line.strip()

    parts = [p for p in [univ, branch] if p]
    title = " - ".join(parts) if parts else "University Academic Syllabus"
    if pattern and pattern not in title:
        title += f" ({pattern})"
    return title


def _extract_department(full_text: str) -> str:
    match = re.search(r'(Department of [^\n]+|Faculty of [^\n]+)', full_text, re.IGNORECASE)
    if match:
        dept = match.group(1).strip()
        return re.sub(r'\s+', ' ', dept)
    return "Electronics & Telecommunication Engineering"


def _extract_academic_year(full_text: str) -> str:
    match = re.search(r'(?:Academic Year\s+|AY\s*)(\d{4}[–\-]\d{2,4})', full_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match_fallback = re.search(r'\b(20\d{2}[–\-]\d{2,4})\b', full_text)
    if match_fallback:
        return match_fallback.group(1).strip()
    return "2025-26"


def _extract_program_outcomes(full_text: str, pages_data: List[Dict]) -> List[Dict[str, str]]:
    """Extract PO1..PO12 and PSO1..PSO5 from syllabus pages with full titles and descriptions."""
    outcomes = []
    seen_codes = set()

    # Search specifically in pages mentioning POs first
    po_pages_text = ""
    for p in pages_data:
        t = p["text"]
        if re.search(r'Program\s+Outcomes|Programme\s+Outcomes|Graduate\s+Attributes|Programme\s+Educational\s+Objectives|\bPOs\b', t, re.IGNORECASE):
            po_pages_text += "\n" + t

    if not po_pages_text.strip():
        po_pages_text = full_text

    lines = po_pages_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        match = re.match(r'^(?:[\W\d_]+)?(PO\s*\d+|PSO\s*\d+)\b[\s:\-\–\.]*(.*)', line, re.IGNORECASE)
        if match:
            code = re.sub(r'\s+', '', match.group(1).upper())
            rest = match.group(2).strip()
            rest = re.sub(r'^[:\-–\s]+', '', rest).strip()

            desc_parts = [rest] if rest else []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt:
                    j += 1
                    continue
                # Stop if next line is another PO or major section boundary
                if re.match(r'^(?:[\W\d_]+)?(PO\s*\d+|PSO\s*\d+)\b', nxt, re.IGNORECASE) or re.match(r'^(?:[\W\d_]+)?(Course|Unit|Semester|Reference|Contents|General\s+Rules|Guidelines)\b', nxt, re.IGNORECASE):
                    break
                # Skip standalone page numbers or Roman numerals
                if re.match(r'^\d+$|^[i|v|x]+$', nxt, re.IGNORECASE):
                    j += 1
                    continue
                desc_parts.append(nxt)
                j += 1

            full_desc = clean_word_hyphenation(desc_parts)
            full_desc = re.sub(r'^[:\-–\s]+', '', full_desc).strip()

            # Standardize title if present (e.g. "Engineering Knowledge Apply knowledge..." -> "Engineering Knowledge: Apply knowledge...")
            title_match = re.match(
                r'^(Engineering Knowledge|Problem Analysis|Design\s*/\s*Development of Solutions|Conduct Investigations of Complex Problems|Engineering Tool Usage|The Engineer and the World|Ethics|Individual and Collaborative Team Work|Communication|Project Management and Finance|Life-Long Learning)\s*(.*)',
                full_desc,
                flags=re.IGNORECASE
            )
            if title_match:
                po_title = title_match.group(1).strip()
                po_body = title_match.group(2).strip()
                po_body = re.sub(r'^[:\-–\s]+', '', po_body).strip()
                full_desc = f"{po_title}: {po_body}" if po_body else po_title

            if code not in seen_codes and len(full_desc) > 5:
                seen_codes.add(code)
                outcome_type = "PSO" if code.startswith("PSO") else "PO"
                outcomes.append({
                    "outcome_code": code,
                    "outcome_type": outcome_type,
                    "description": full_desc
                })

            i = j - 1
        i += 1


    # Sort numerically (PO1, PO2, ... PO11)
    outcomes.sort(key=lambda x: (
        x["outcome_type"],
        int(re.search(r'\d+', x["outcome_code"]).group(0)) if re.search(r'\d+', x["outcome_code"]) else 0
    ))
    return outcomes


def _extract_courses_and_cos(full_text: str, pages_data: List[Dict]) -> List[Dict[str, any]]:
    """
    Extract courses (e.g. PCC-201-ETC) and their Course Outcomes (CO1..CO6).
    Handles flexible hyphenation, spaced course codes (e.g. EEM-283- ETC),
    and prevents curriculum overview tables from corrupting course names.
    """
    courses = []

    # Pattern 1: PCC-201-ETC: Electronics Circuits or EEM-283- ETC : Entrepreneurship...
    header_pattern1 = re.compile(
        r'\b([A-Z]{2,5}\s*[-–]\s*\d{3}(?:\s*[-–]\s*[A-Z0-9]+)?)\b[\s:\-–]+([^\n]+)',
        re.IGNORECASE
    )

    # Pattern 2: Course Code : 204181 Course Name : Digital Electronics
    header_pattern2 = re.compile(
        r'Course\s+Code\s*[:\-–]?\s*([A-Z0-9\-]+)\s*Course\s+Name\s*[:\-–]?\s*([^\n]+)',
        re.IGNORECASE
    )

    # Pattern 3: CS201: Data Structures
    header_pattern3 = re.compile(
        r'\b([A-Z]{2,4}\d{3,4})\b[\s:\-–]+([^\n]+)',
        re.IGNORECASE
    )

    current_course = None

    for p in pages_data:
        text = p["text"]
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue

            code_raw = None
            name_raw = None

            # Check Match Pattern 2
            m2 = header_pattern2.search(line_str)
            if m2:
                code_raw = m2.group(1).upper()
                name_raw = m2.group(2).strip()
            else:
                # Check Match Pattern 1
                m1 = header_pattern1.search(line_str)
                if m1:
                    code_raw = m1.group(1).upper().strip()
                    name_raw = m1.group(2).strip()
                else:
                    m3 = header_pattern3.search(line_str)
                    if m3:
                        code_raw = m3.group(1).upper().strip()
                        name_raw = m3.group(2).strip()

            if code_raw and name_raw:
                # Normalize code: remove internal spaces, normalize hyphens
                norm_code = re.sub(r'\s+', '', code_raw).replace('–', '-')

                # Filter out non-course codes
                if not re.match(r'^(NEP|SE|TE|BE|LEVEL|PAGE|TABLE|UNIT|AY|AY-20\d\d)', norm_code):
                    # Clean up course name
                    clean_name = re.sub(
                        r'[\s:\-–]*(Teaching\s+Scheme|Credits|Semester|Level|Hours|Marks|Examination).*',
                        '', name_raw, flags=re.IGNORECASE
                    ).strip()
                    # Strip residual code prefix e.g. "ETC : " or "- ETC -"
                    clean_name = re.sub(r'^[A-Z]{2,4}\s*[:\-–]+\s*', '', clean_name)
                    clean_name = re.sub(r'^[:\-–\s]+', '', clean_name).strip()

                    # Avoid summary table rows that contain long series of digits/grades (e.g. 3 - - 30 70 - - - 100 3 - - 3)
                    is_table_row = bool(re.search(r'\d+\s+[-–\d]+\s+[-–\d]+\s+\d{2,3}', clean_name))

                    # Check if this line looks like an authoritative course header on a course page
                    is_authoritative_page = False
                    for look_ahead in lines[i+1:i+5]:
                        if re.search(r'(Teaching\s+Scheme|Credits|Examination\s+Scheme|Prerequisite|Course\s+Objectives|Course\s+Outcomes)', look_ahead, re.IGNORECASE):
                            is_authoritative_page = True
                            break

                    if is_authoritative_page or not is_table_row:
                        # Clean further if table row remnants
                        clean_name = re.sub(r'\s+\d+\s+[-–\d]+.*$', '', clean_name).strip()
                        # Also strip "Program Core Course - ", "Program Core Course", etc.
                        clean_name = re.sub(
                            r'^(Program\s+Core\s+Course(?:-Lab)?|Multi[\s\-]?disciplinary\s+Minor(?:-Lab)?|Open\s+Elective(?:\s*-\s*[I|V|X\d]+)?|Value\s+Education(?:-Lab)?|Vocational\s+and\s+Skill\s+Enhancement\s+Course|Ability\s+Enhancement\s+Course)\s*[:\-–]?\s*',
                            '', clean_name, flags=re.IGNORECASE
                        ).strip()

                        if clean_name and len(clean_name) > 2 and not clean_name.lower().startswith("course"):
                            existing = next((c for c in courses if c["course_code"] == norm_code), None)
                            if not existing:
                                current_course = {
                                    "course_code": norm_code,
                                    "course_name": clean_name,
                                    "semester": None,
                                    "course_outcomes": []
                                }
                                courses.append(current_course)
                            else:
                                current_course = existing
                                # Update name if this is the authoritative course page or cleaner
                                if is_authoritative_page or len(clean_name) < len(existing["course_name"]):
                                    existing["course_name"] = clean_name

            # Look for CO lines: CO1: ... or 1. CO1 - ... or • CO1: ... or • CO1. ... (allow description on same line or next line)
            co_match = re.match(r'^(?:[\W\d_]+)?(CO\s*\d+)\b[\s:\-\–\.]*(.*)', line_str, re.IGNORECASE)
            if co_match and current_course:
                co_code = re.sub(r'\s+', '', co_match.group(1).upper())
                co_desc_same_line = co_match.group(2).strip()
                co_desc_same_line = re.sub(r'^[:\-–\s]+', '', co_desc_same_line).strip()

                # Collect continuation lines
                j = i + 1
                desc_lines = [co_desc_same_line] if co_desc_same_line else []
                while j < len(lines):
                    nxt = lines[j].strip()
                    if not nxt:
                        j += 1
                        continue

                    # Stop if next line is another CO
                    if re.match(r'^(?:[\W\d_]+)?CO\s*\d+\b', nxt, re.IGNORECASE):
                        break

                    # Stop if next line is a major section header
                    if re.match(
                        r'^(?:[\W\d_]+)?(Course\s+Contents|Contents|Unit\s+[IVX\d]+|Tutorial|Laboratory|Practical|Experiments|Suggested\s+List|List\s+of|Part\s+[A-Z\d]|Section\s+[A-Z\d]|Mapping\s+of|Prerequisite|Companion|Learning\s+Resources|Textbooks|Reference\s+Books|Books|MOOC|Web\s+Resources|Guidelines|Exemplar|Teaching\s+Scheme|Examination\s+Scheme|Credits)\b',
                        nxt,
                        re.IGNORECASE
                    ):
                        break

                    # Skip standalone page numbers or Roman numerals
                    if re.match(r'^\d+$|^[i|v|x]+$', nxt, re.IGNORECASE):
                        j += 1
                        continue

                    desc_lines.append(nxt)
                    j += 1

                full_co_desc = clean_word_hyphenation(desc_lines)
                full_co_desc = re.sub(r'^[:\-–\s]+', '', full_co_desc).strip()
                # Clean off accidental trailing tutorial/lab/course content text
                full_co_desc = re.split(r'\b(?:Tutorial\s+shall|Laboratory\s+Assignments|Suggested\s+List|Course\s+Contents|List\s+of\s+Practical)\b', full_co_desc, flags=re.IGNORECASE)[0].strip()

                # Avoid duplicate CO entries
                existing_co = next((c for c in current_course["course_outcomes"] if c["co_code"] == co_code), None)
                if not existing_co:
                    if len(full_co_desc) > 3:
                        current_course["course_outcomes"].append({
                            "co_code": co_code,
                            "description": full_co_desc
                        })
                else:
                    # If existing description was very brief, replace with fuller one
                    if len(full_co_desc) > len(existing_co["description"]) + 10:
                        existing_co["description"] = full_co_desc

    # Return courses that contain COs (or all if none yet)
    courses_with_cos = [c for c in courses if len(c["course_outcomes"]) > 0]
    return courses_with_cos if courses_with_cos else courses
