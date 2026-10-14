"""
PDF Syllabus Parser — Automatically extracts POs, PSOs, Courses, and COs from University Syllabus PDFs.
Specifically optimized for SPPU, AICTE, and NEP-2020 engineering curriculum structures across all years (FE, SE, TE, BE).
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
    1. Framework Metadata (Title, Department, Academic Year, Year Level)
    2. Program Outcomes (POs) & Program Specific Outcomes (PSOs)
    3. Courses and their respective Course Outcomes (COs)
    """
    pages_data = extract_text_from_pdf(file_path)
    full_text = "\n".join([p["text"] for p in pages_data])

    # 1. Detect Year Level (FE, SE, TE, BE)
    detected_year = _detect_year_level(full_text, pages_data)
    final_year = detected_year

    # 2. Extract Framework Metadata
    framework_name = _extract_framework_title(full_text, pages_data, final_year)
    department = _extract_department(full_text)
    academic_year = _extract_academic_year(full_text)

    # 3. Extract Program Outcomes (POs) & PSOs
    pos = _extract_program_outcomes(full_text, pages_data)

    # 4. Extract Courses & Course Outcomes (COs)
    courses = _extract_courses_and_cos(full_text, pages_data, final_year)

    logger.info(
        f"Parsed PDF syllabus: Framework='{framework_name}', Year='{final_year}', "
        f"POs count={len(pos)}, Courses count={len(courses)}"
    )

    return {
        "framework_name": framework_name,
        "department": department,
        "academic_year": academic_year,
        "year": final_year,
        "program_outcomes": pos,
        "courses": courses,
    }


def _detect_year_level(full_text: str, pages_data: List[Dict]) -> str:
    """Detect whether syllabus is for FE, SE, TE, or BE."""
    first_pages_text = "\n".join([p["text"] for p in pages_data[:12]])

    # Look for unambiguous year mentions near the beginning
    if re.search(r'\b(First\s+Year|F\.?E\.?|Semester\s+[I|1]\b|Semester\s+II\b)\b', first_pages_text, re.IGNORECASE):
        return "FE"
    if re.search(r'\b(Second\s+Year|S\.?E\.?|Semester\s+III\b|Semester\s+IV\b)\b', first_pages_text, re.IGNORECASE):
        return "SE"
    if re.search(r'\b(Third\s+Year|T\.?E\.?|Semester\s+V\b|Semester\s+VI\b)\b', first_pages_text, re.IGNORECASE):
        return "TE"
    if re.search(r'\b(Final\s+Year|Fourth\s+Year|B\.?E\.?|Semester\s+VII\b|Semester\s+VIII\b)\b', first_pages_text, re.IGNORECASE):
        return "BE"

    return "BE"


def _extract_framework_title(full_text: str, pages_data: List[Dict], year_level: str) -> str:
    """Extract syllabus title (e.g. SPPU - TE Information Technology (2024 Pattern))."""
    pat_match = re.search(r'(\d{4}\s*Course|\d{4}\s*Pattern|\bNEP[-\s]*2020\b)', full_text, re.IGNORECASE)
    pattern_str = pat_match.group(0).strip() if pat_match else ("2024 Pattern" if year_level == "TE" else "2019 Course")

    dept = _extract_department(full_text)
    return f"SPPU - {year_level} {dept} ({pattern_str})"


def _extract_department(full_text: str) -> str:
    if re.search(r'Information\s+Technology', full_text, re.IGNORECASE):
        return "Information Technology"
    if re.search(r'Computer\s+Engineering', full_text, re.IGNORECASE):
        return "Computer Engineering"
    match = re.search(r'(Department of [^\n]+|Faculty of [^\n]+)', full_text, re.IGNORECASE)
    if match:
        dept = match.group(1).strip()
        return re.sub(r'\s+', ' ', dept)
    return "Information Technology"


def _extract_academic_year(full_text: str) -> str:
    match = re.search(r'(?:Academic Year\s+|AY\s*)(\d{4}[–\-]\d{2,4})', full_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match_fallback = re.search(r'\b(20\d{2}[–\-]\d{2,4})\b', full_text)
    if match_fallback:
        return match_fallback.group(1).strip()
    return "2024-25"


def _extract_program_outcomes(full_text: str, pages_data: List[Dict]) -> List[Dict[str, str]]:
    """
    Extract PO1..PO12 and PSO1..PSO4 from syllabus pages with full titles and descriptions.
    Works for both traditional tabular formats and modern NEP-2020 text structures.
    """
    po_text = ""
    # Collect text from pages that mention POs, PSOs, Graduate Attributes, or specific PO/PSO markers
    for p in pages_data[:20]:
        t = p["text"]
        if re.search(r'Program(?:me)?\s+(?:Specific\s+)?Outcomes|Graduate\s+Attributes|Programme\s+Educational\s+Objectives|\bPOs?\b|\bPSOs?\b|\bPO\s*\d+\b|\bPSO\s*\d+\b', t, re.IGNORECASE):
            po_text += "\n" + t

    if not po_text.strip():
        po_text = full_text

    pattern_po = re.compile(r'^\s*(?:[\W\d_]+)?\b(PO\s*\d+|PSO\s*\d+)\b[\s:\-–\.]*(.*)', re.IGNORECASE | re.MULTILINE)
    lines_po = po_text.split('\n')
    outcomes = []
    seen_codes = set()

    i = 0
    while i < len(lines_po):
        line = lines_po[i].strip()
        m = pattern_po.match(line)
        if m:
            code = re.sub(r'\s+', '', m.group(1).upper())
            rest = m.group(2).strip()
            desc_lines = [rest] if rest else []

            j = i + 1
            while j < len(lines_po):
                nxt = lines_po[j].strip()
                if not nxt:
                    j += 1
                    continue
                # Stop if next line is another PO or major section boundary
                if pattern_po.match(nxt) or re.match(r'^(?:[\W\d_]+)?(Course|Unit|Semester|Reference|Table|Knowledge|Faculty|NEP|Abbreviations)\b', nxt, re.IGNORECASE):
                    break
                # Skip standalone page numbers or Roman numerals
                if re.match(r'^\d+$|^[ivx]+$', nxt, re.IGNORECASE):
                    j += 1
                    continue
                desc_lines.append(nxt)
                j += 1

            raw_desc = clean_word_hyphenation(desc_lines)

            # Clean duplicate titles in description (common in multi-column tables, e.g. "Engineering Knowledge: Engineering Knowledge: Apply ...")
            clean_desc = re.sub(
                r'^(?:Engineering\s+knowledge|Problem\s+analysis|Design\s*/\s*Development\s+of\s+Solutions|Conduct\s+Investigations?\s+of\s+Complex\s+Problems|Engineering\s+Tool\s+Usage|Modern\s+Tool\s+Usage|The\s+Engineer\s+and\s+The\s+World|The\s+Engineer\s+and\s+Society|Ethics|Individual\s+and\s+Collaborative\s+Team\s*work|Individual\s+and\s+Team\s*Work|Communication|Communication\s+Skills|Project\s+Management\s+and\s+Finance|Life[- ]Long\s+Learning)\s*',
                '',
                raw_desc,
                flags=re.IGNORECASE
            )
            clean_desc = re.sub(r'^[:\-–\s]+', '', clean_desc).strip()

            # Format with canonical title prefix if recognized
            title_m = re.match(
                r'^(Engineering Knowledge|Problem Analysis|Design\s*/\s*Development of Solutions|Conduct Investigations? of Complex Problems|Engineering Tool Usage|Modern Tool Usage|The Engineer and The World|The Engineer and Society|Ethics|Individual and Collaborative Team work|Individual and Team Work|Communication|Communication Skills|Project Management and Finance|Life[- ]Long Learning)\s*[:\-–]?(.*)',
                clean_desc,
                re.IGNORECASE
            )
            if title_m:
                po_title = title_m.group(1).strip()
                po_body = title_m.group(2).strip()
                po_body = re.sub(r'^[:\-–\s]+', '', po_body).strip()
                clean_desc = f"{po_title}: {po_body}" if po_body else po_title

            clean_desc = re.sub(r'^[:\-–\s]+', '', clean_desc).strip()

            if code not in seen_codes and len(clean_desc) > 8:
                seen_codes.add(code)
                otype = "PSO" if "PSO" in code else "PO"
                outcomes.append({
                    "outcome_code": code,
                    "outcome_type": otype,
                    "description": clean_desc
                })

            i = j - 1
        i += 1

    # Sort numerically (PO1, PO2, ..., PSO1, PSO2...)
    outcomes.sort(key=lambda x: (
        x["outcome_type"],
        int(re.search(r'\d+', x["outcome_code"]).group(0)) if re.search(r'\d+', x["outcome_code"]) else 0
    ))
    return outcomes


def _extract_courses_and_cos(full_text: str, pages_data: List[Dict], default_year: str = "BE") -> List[Dict[str, any]]:
    """
    Extract all courses and their Course Outcomes (COs).
    Supports:
    - 2024 NEP-2020 Multi-line headers: 'Course Code: PCC-301-ITT' \n 'Course Name: Operating System'
    - 2019 SPPU 6-digit codes: '414441: Information Storage and Retrieval'
    - Hyphenated headers: 'PCC-301-IT - Operating System'
    - Single-line headers: 'Course Code: 414441 Course Name: ...'
    - Standard COs (CO1..CO6), hyphenated COs (CO-1..CO-5), and bulleted/numbered outcomes.
    """
    courses = []
    
    sem_year_map = {
        'Semester I': 'FE', 'Semester II': 'FE',
        'Semester III': 'SE', 'Semester IV': 'SE',
        'Semester V': 'TE', 'Semester VI': 'TE',
        'Semester VII': 'BE', 'Semester VIII': 'BE'
    }

    current_sem = "Semester V" if default_year == "TE" else ("Semester VII" if default_year == "BE" else ("Semester III" if default_year == "SE" else "Semester I"))

    for pidx, p in enumerate(pages_data):
        text = p["text"]
        
        # Track semester boundaries
        sem_m = re.search(r'SEMESTER\s*[-–:]?\s*(VIII|VII|VI|IV|III|II|V|I)\b', text, re.IGNORECASE)
        if sem_m:
            current_sem = f"Semester {sem_m.group(1).upper()}"

        c_code = None
        c_name = None

        # 1. Multi-line or single-line: Course Code: ... Course Name: ...
        code_m = re.search(r'Course\s+Code\s*[:\-–]\s*([A-Za-z0-9\s\-]+?)(?=\s+Course\s+Name|\n|$)', text, re.IGNORECASE)
        name_m = re.search(r'Course\s+Name\s*[:\-–]\s*([^\n]+)', text, re.IGNORECASE)
        if code_m and name_m:
            raw_c = code_m.group(1).strip()
            raw_n = name_m.group(1).strip()
            clean_c = re.sub(r'\s+', '-', raw_c).replace('--', '-')
            if not re.search(r'Course|Teaching|Scheme', clean_c, re.IGNORECASE) and len(clean_c) >= 3:
                c_code = clean_c
                c_name = raw_n

        # 2. SPPU 6-digit format: 414441: Information Storage and Retrieval
        if not c_code:
            sppu_m = re.search(r'^\s*(\b\d{6}[A-Z]?\b)\s*[:\-–]\s*([^\n]+)', text, re.MULTILINE)
            if sppu_m:
                c_code = sppu_m.group(1).strip()
                c_name = sppu_m.group(2).strip()

        # 3. Code-Hyphen-Name: PCC-301-IT - Operating System
        if not c_code:
            hyphen_m = re.search(r'^\s*([A-Z]{2,4}\s*[-–]\s*\d{3}[A-Z0-9\s\-]*(?:\s*[-–]\s*[A-Z0-9]+)?)\s*[:\-–]\s*([^\n]+)', text, re.MULTILINE)
            if hyphen_m:
                raw_c = hyphen_m.group(1).strip()
                if not re.match(r'^(NEP|SE|TE|BE|UNIT|PAGE|TABLE)', raw_c, re.IGNORECASE):
                    c_code = re.sub(r'\s+', '', raw_c)
                    c_name = hyphen_m.group(2).strip()

        if c_code and c_name:
            # Clean up course name
            clean_name = re.split(
                r'\b(Teaching\s+Scheme|Credit|Examination|Prerequisite|Credits|Course\s+Objectives)\b',
                c_name,
                flags=re.IGNORECASE
            )[0].strip()
            clean_name = re.sub(r'^[:\-–\s]+', '', clean_name).strip()
            clean_name = re.sub(
                r'^(Program\s+Core\s+Course(?:-Lab)?|Multi[\s\-]?disciplinary\s+Minor(?:-Lab)?|Open\s+Elective(?:\s*-\s*[I|V|X\d]+)?|Value\s+Education(?:-Lab)?|Vocational\s+and\s+Skill\s+Enhancement\s+Course|Ability\s+Enhancement\s+Course)\s*[:\-–]?\s*',
                '',
                clean_name,
                flags=re.IGNORECASE
            ).strip()

            # Ignore table of contents / syllabus summary lines
            if re.search(r'\d+\s+[-–\d]+\s+[-–\d]+\s+\d{2,3}', clean_name) or len(clean_name) <= 2:
                continue

            # Resolve year
            year = sem_year_map.get(current_sem, default_year)

            # Extract COs specifically from the Course Outcomes section or current page
            cos = _extract_cos_from_page(text)

            # Check next page if no COs found on this page (sometimes course header is on p1 and COs on p2)
            if not cos and pidx + 1 < len(pages_data):
                next_text = pages_data[pidx + 1]["text"]
                # Only check next page if next page is NOT a new course
                if not re.search(r'Course\s+Code\s*[:\-–]|^\s*\b\d{6}[A-Z]?\b\s*[:\-–]', next_text, re.MULTILINE):
                    cos = _extract_cos_from_page(next_text)

            # Disambiguate duplicate elective codes (e.g. 414444 Mobile Computing vs HPC)
            unique_code = c_code
            if any(c["course_code"] == unique_code for c in courses):
                sub_match = re.search(r'\(([^)]+)\)', clean_name)
                if sub_match:
                    sub_text = sub_match.group(1)
                    abbr = ''.join([w[0] for w in sub_text.split() if w[0].isalnum()]).upper()
                    cand_code = f"{c_code}-{abbr}"
                else:
                    cand_code = f"{c_code}-2"
                counter = 1
                while any(c["course_code"] == cand_code for c in courses):
                    counter += 1
                    cand_code = f"{c_code}-{counter}"
                unique_code = cand_code

            courses.append({
                "course_code": unique_code,
                "course_name": clean_name,
                "year": year,
                "semester": current_sem,
                "division": "All",
                "course_outcomes": cos
            })

    # Filter to courses with extracted Course Outcomes
    valid_courses = [c for c in courses if len(c["course_outcomes"]) > 0]
    return valid_courses if valid_courses else courses


def _extract_cos_from_page(page_text: str) -> List[Dict[str, str]]:
    """
    Extracts COs (CO1..CO6) from a page's text.
    Handles explicit CO labels as well as bulleted/numbered lists under Course Outcomes.
    """
    cos = []
    
    # Isolate Course Outcomes block to prevent matching mapping tables / unit contents
    co_sec = re.search(
        r'Course\s+Outcomes\s*[:\-–]?(.*?)(?=COURSE\s+CONTENTS|Course\s+Contents|Guidelines|Unit\s+No|Unit\s+I\b|Learning\s+Resources|Books|$)',
        page_text,
        re.DOTALL | re.IGNORECASE
    )
    search_scope = co_sec.group(1) if co_sec else page_text

    lines = [l.strip() for l in search_scope.split('\n') if l.strip()]
    curr_code = None
    curr_parts = []
    
    co_pat = re.compile(r'^(?:[^\w\s]|[\uf0b7\u25cf\u2022\*\-–\d\.\s])*\b(CO[\s\-–\.]*\d+)\b[\s:\-–\.]*(.*)', re.IGNORECASE)

    for line in lines:
        clean_l = re.sub(r'^[^\w\s]+', '', line).strip()
        if clean_l.lower().startswith(('on completion of', 'after successful completion', 'upon successful completion', 'learners are expected')):
            continue
        m = co_pat.match(line)
        if m:
            if curr_code and curr_parts:
                cos.append({
                    "co_code": curr_code,
                    "description": clean_word_hyphenation(curr_parts)
                })
            curr_code = re.sub(r'[\s\-–\.]+', '', m.group(1).upper())
            rest = m.group(2).strip()
            curr_parts = [rest] if rest else []
        elif curr_code:
            # Stop if encountering unit or section marker
            if re.match(r'^(?:Unit\s+No|Unit\s+[IVX\d]+|Guidelines|Exemplars?|Part\s+[A-Z\d]|Course\s+Contents)\b', clean_l, re.IGNORECASE):
                break
            curr_parts.append(line)

    if curr_code and curr_parts:
        cos.append({
            "co_code": curr_code,
            "description": clean_word_hyphenation(curr_parts)
        })

    # If no explicit CO prefix was found, try bullet/number splitting under Course Outcomes
    if not cos and co_sec:
        items = re.split(r'\n\s*(?:[^\w\s\n]|[\uf0b7\u25cf\u2022\*\-–]|(?:CO[\s\-–\.]*)?\d+[\.:\)\-–])\s*', '\n' + search_scope)
        valid_items = [
            clean_word_hyphenation([it]) for it in items
            if len(it.strip()) > 15 and not re.sub(r'^[^\w\s]+', '', it).strip().lower().startswith(('on completion', 'after successful', 'upon successful', 'course outcomes'))
        ]
        for idx, it in enumerate(valid_items, 1):
            cos.append({
                "co_code": f"CO{idx}",
                "description": it
            })

    return cos
