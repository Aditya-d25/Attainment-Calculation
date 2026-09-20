# Outcome Studio — CO–PO/PSO Mapping & Attainment Workspace

An explainable, faculty-in-the-loop CO–PO/PSO matrix generation and outcome attainment platform for higher education institutions (SPPU, AICTE, NEP-2020).

---

## 🌟 Key Features

- 🎓 **Programme Framework Catalogue**: Define Program Outcomes (POs) and Program Specific Outcomes (PSOs) centrally per department/stream pattern. Every course linked to the framework reuses canonical definitions.
- 📄 **Automated PDF Syllabus Parsing**: Drag-and-drop university syllabus PDFs to automatically extract framework metadata, department, academic year, POs/PSOs, course codes, and Course Outcomes (COs).
- 🤖 **Hybrid AI Mapping Engine**:
  - **Semantic Vector Matcher**: Computes TF-IDF & cosine similarity for candidate pair identification.
  - **LLM Reasoning**: Leverages Google Gemini AI to analyze Bloom's Taxonomy verbs, contextual alignment, and output detailed justifications.
  - **Fallback Accreditation Engine**: Automatic fallback to deterministic pedagogical rules if offline or if LLM quota is reached.
- 🔄 **Faculty-in-the-Loop & Adaptive Calibration**:
  - **Cell Inspection**: Single-click any matrix cell to view reasoning, evidence snippet, semantic score, and confidence level.
  - **Manual Override**: Double-click cell to override level (0–3) and record faculty review notes.
  - **Feedback Learning**: Historical faculty overrides are retrieved as few-shot calibration examples for subsequent generations in the same framework.
- 📊 **Comprehensive Excel Reports**: Export complete `.xlsx` reports containing the generated & finalized matrix, outcome catalogues, detailed cell explanations, and audit feedback logs.

---

## 🛠️ Technology Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10+)
- **Database / ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) (SQLite by default, MySQL compatible)
- **AI & NLP**: [Google Generative AI (Gemini)](https://ai.google.dev/), Scikit-Learn (TF-IDF), PyPDF
- **Frontend**: Vanilla HTML5, CSS3 (Modern Glassmorphism UI, Responsive Dashboard), Modern JavaScript
- **Reporting**: OpenPyXL (`.xlsx` generation)

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10 or higher
- Git

### 2. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the project root (or copy `.env.example`):
```env
DATABASE_URL=sqlite:///./test.db
GEMINI_API_KEY=your_gemini_api_key_here
MOCK_MODE=false
```
*Note: If `GEMINI_API_KEY` is not provided or quota is exceeded, the system automatically uses the fallback accreditation rule engine.*

### 4. Run Application
```bash
uvicorn main:app --reload
```
Open your browser and navigate to **`http://127.0.0.1:8000`**.

---

## 📋 Faculty Workflow

1. **Select or Import Framework**: Choose an existing Programme Framework or import a syllabus PDF to automatically extract POs, PSOs, and Courses.
2. **Add / Review Course Outcomes**: View extracted COs for a course or manually add measurable outcomes.
3. **Generate Mapping Matrix**: Click **Generate Matrix**. The hybrid AI engine analyzes CO–PO/PSO alignment.
4. **Inspect & Adjust**:
   - Click a matrix cell to inspect AI reasoning, semantic similarity, and confidence score.
   - Edit cell value (0 to 3) to overwrite level and provide faculty notes.
5. **Export Report**: Download the complete `.xlsx` outcome mapping report.

---

## 📐 Mapping Scale Reference

| Level | Contribution | Description |
| :---: | :--- | :--- |
| **3** | **High / Direct** | Strong direct alignment with Bloom's taxonomy verbs and learning outcomes |
| **2** | **Moderate** | Meaningful contribution to outcome achievement |
| **1** | **Low / Indirect** | Indirect or supporting relationship |
| **0** | **None** | No meaningful relationship |

---

## 📂 Project Architecture

```
├── main.py                   # FastAPI application entrypoint & static mounting
├── models.py                 # SQLAlchemy ORM database models
├── schemas.py                # Pydantic schemas for API request/response validation
├── database.py               # Database engine & session configuration
├── ai/
│   ├── mapper.py             # Hybrid AI mapping coordinator pipeline
│   ├── llm_reasoner.py       # Gemini LLM integration with rate-limit handling & retry backoff
│   └── validator.py          # Matrix mapping validation rules
├── routers/
│   ├── frameworks.py         # Programme Framework API endpoints
│   ├── subjects.py           # Subject & CO management API endpoints
│   ├── mapping.py            # AI Matrix generation & cell review endpoints
│   ├── pdf.py                # PDF syllabus upload & parsing endpoints
│   └── excel.py              # XLSX report export endpoints
├── services/
│   ├── pdf_parser.py         # Regex & PyPDF parser for university syllabi (SPPU, AICTE, NEP)
│   └── mapping_service.py    # Business logic for mapping generation & persistent storage
├── frontend/
│   ├── templates/index.html  # Main single-page application dashboard
│   └── static/
│       ├── app.js            # Interactive UI logic & state management
│       └── style.css         # Glassmorphism styling system & layout
└── tests/                    # Pytest unit & integration test suites
```

---

## 🧪 Running Tests

To run the automated test suite:
```bash
pytest tests/
```

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
