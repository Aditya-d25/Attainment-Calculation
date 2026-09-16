# Attainment-Calculation: AI-Based Automated CO-PO Mapping & Outcome Attainment Engine

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg?logo=python)](https://www.python.org/)
[![MySQL](https://img.shields.io/badge/Database-MySQL-4479A1.svg?logo=mysql)](https://www.mysql.com/)
[![Gemini](https://img.shields.io/badge/AI%20Model-Gemini%203.6%20Flash-orange.svg?logo=google)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-Academic%20Project-green.svg)]()

An end-to-end outcome-based education (OBE) platform for automatically generating, reviewing, and calculating **Course Outcome (CO) to Program Outcome (PO/PSO)** mappings and **outcome attainments** using a hybrid Dense Vector Embedding (`all-MiniLM-L6-v2`) and Large Language Model (`Google Gemini 3.6 Flash`) reasoning pipeline.

---

## 📌 Problem Statement

In Outcome-Based Education (OBE) and NBA accreditation, faculty members must manually map each Course Outcome (CO) to 12 Program Outcomes (POs) and several Program Specific Outcomes (PSOs). This process is:
- **Time-consuming and subjective**: prone to faculty bias and inconsistent mapping levels across departments.
- **Difficult to justify**: lacking concrete evidence and Bloom's Taxonomy reasoning.
- **Complex to compute**: requiring manual calculation of University Exam attainments, Continuous Internal Evaluations (CIE), and weighted PO attainments across matrices.

---

## 💡 Solution Overview

This system provides a unified web-based workflow:
1. **Automated AI Mapping**: Extracts Bloom's verbs and domain concepts, computes dense vector cosine similarities, and applies Gemini 3.6 Flash reasoning with semantic fallback to determine relationship levels (0–3) with explanations and confidence scores.
2. **Outcome Attainment Engine**: Computes Course Outcome attainments and overall Program Outcome attainments using standardized NBA weighted formulas with real-time recalculation.
3. **Faculty-in-the-Loop Review**: Human approval workflow allowing faculty to accept, edit, or reject AI suggestions.
4. **Evaluation & Comparison**: Benchmarks AI outputs against historical faculty ground truth using accuracy, precision, recall, F1, and confusion matrices.
5. **Excel Integration**: Imports reference Excel sheets and exports full accreditation-ready reports.

---

## 🏗️ System Architecture

```
                      Course Outcome (CO) & Program Outcome (PO/PSO) Text
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │ 1. Text Preprocessor                      │
                         │    • Normalize text & strip boilerplate   │
                         │    • Extract Bloom's Taxonomy verbs       │
                         │    • Extract domain keywords & concepts   │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │ 2. Semantic Embedding & Similarity        │
                         │    • Model: all-MiniLM-L6-v2 (384-dim)    │
                         │    • Pairwise Cosine Similarity Matrix    │
                         │    • Candidate generation (threshold >0.2)│
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │ 3. LLM Contextual Reasoner                │
                         │    • Google Gemini 3.6 Flash API          │
                         │    • Generates Level (0–3) & Justification│
                         │    • Semantic fallback on rate limits     │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │ 4. Validation & Quality Agent             │
                         │    • Enforces constraints & ranges        │
                         │    • Auto-fixes format anomalies          │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │ 5. Outcome Attainment Engine              │
                         │    • Total CO Attainment: (a*0.6)+(b*0.4) │
                         │    • PO Attainment: Σ(CO_att*Lvl) / Σ(Lvl)│
                         │    • Real-time editable matrix interface  │
                         └─────────────────────┬─────────────────────┘
                                               │
                                               ▼
                         ┌───────────────────────────────────────────┐
                         │ 6. Faculty Review & Benchmark Evaluation  │
                         │    • Accept / Edit / Reject workflow      │
                         │    • Accuracy, F1, Confusion Matrix vs Ref│
                         │    • Excel import / export                │
                         └───────────────────────────────────────────┘
```

---

## 📐 Mathematical Formulas

### 1. Total Course Outcome (CO) Attainment
Total attainment for each Course Outcome is calculated as the weighted sum of University Result and Continuous Internal Evaluation (CCE):

$$\text{Total CO Attainment} = (a \times 0.6) + (b \times 0.4)$$

Where:
- **$a$**: CO Attainment Level through University Result (displays `⚠️` alert if pending/0.0)
- **$b$**: CO Attainment Level through Internal Assessment-CCE

### 2. Program Outcome (PO / PSO) Attainment
The final attainment for each Program Outcome (PO1–PO11, PSO1–PSO3) is computed using weighted mapping levels:

$$\text{PO Attainment} = \frac{\sum_{i=1}^{N} \Big(\text{CO Attainment}_i \times \text{Mapping Level}_i\Big)}{\sum_{i=1}^{N} \text{Mapping Level}_i}$$

Where:
- $\text{Mapping Level}_i \in \{1, 2, 3\}$ (Level 0 / no relation is excluded from denominator)
- If a PO has no mapped COs ($\sum \text{Mapping Level} = 0$), attainment is marked as `—`.

---

## 🏷️ Mapping Levels Definition

| Level | Meaning | Description |
|:---:|:---:|:---|
| **3** | **Strong Relationship** | Direct, core alignment between CO activities and the PO requirements. |
| **2** | **Moderate Relationship** | Substantial support, partial coverage, or prerequisite skill for the PO. |
| **1** | **Weak Relationship** | Peripheral or indirect relationship. |
| **0 (`—`)** | **No Relation** | No meaningful semantic or educational relationship. |

---

## 🧰 Technology Stack

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy ORM, Pydantic v2, Uvicorn
- **Database**: MySQL Server
- **AI & NLP**: 
  - Dense Embeddings: `sentence-transformers` (`all-MiniLM-L6-v2`) / scikit-learn TF-IDF fallback
  - Large Language Model: `Google Gemini 3.6 Flash` via Google GenAI API
- **Evaluation**: Scikit-Learn (Macro Precision, Recall, F1, Confusion Matrix)
- **Excel Processing**: OpenPyXL
- **Frontend**: Responsive Single-Page Application (HTML5, Vanilla CSS3 with Dark Theme, Vanilla JavaScript)

---

## 📂 Project Structure

```
Attainment-Calculation/
├── main.py                     # FastAPI entry point & app lifecycle
├── database.py                 # SQLAlchemy database engine & session
├── models.py                   # SQLAlchemy ORM models (Subjects, COs, POs, Mappings)
├── schemas.py                  # Pydantic schemas for request/response validation
├── requirements.txt            # Python dependencies
├── .env.example                # Sample environment variables
│
├── ai/                         # Core AI Pipeline
│   ├── preprocessor.py         # Text normalization & Bloom's verb extraction
│   ├── embeddings.py           # Sentence-transformers & cosine similarity computation
│   ├── mapper.py               # Hybrid mapping orchestrator
│   ├── llm_reasoner.py         # Gemini 3.6 Flash & semantic fallback engine
│   ├── validator.py            # AI output quality & constraint checker
│   └── evaluator.py            # Accuracy, F1, Confusion Matrix metrics
│
├── routers/                    # FastAPI REST API Endpoints
│   ├── subjects.py             # Subject, CO, PO, PSO CRUD & attainment routes
│   ├── mapping.py              # Mapping generation, review & evaluation routes
│   └── excel.py                # Reference Excel upload & evaluation report export
│
├── services/                   # Business Logic
│   ├── mapping_service.py      # Pipeline coordination & database synchronization
│   ├── excel_parser.py         # Parser for faculty reference workbooks
│   └── excel_exporter.py       # Exporter for evaluation & attainment sheets
│
├── frontend/                   # UI Assets
│   ├── templates/index.html    # Single-page application interface
│   └── static/
│       ├── style.css           # Modern dark-themed CSS system
│       └── app.js              # State management & dynamic matrix calculator
│
├── sample_data/                # Sample reference workbooks
│   └── reference_mapping.xlsx  # Sample ground truth mapping for testing
└── tests/                      # Automated Test Suite (52 unit tests)
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.9 or higher
- MySQL Server (running locally or remotely)
- Google Gemini API Key ([Get one here](https://aistudio.google.com/))

### 2. Clone the Repository
```bash
git clone https://github.com/Aditya-d25/Attainment-Calculation.git
cd Attainment-Calculation
```

### 3. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Database Setup
Create MySQL database and user:
```sql
CREATE DATABASE co_po_attainment;
CREATE USER 'attainment'@'localhost' IDENTIFIED BY '1234';
GRANT ALL PRIVILEGES ON co_po_attainment.* TO 'attainment'@'localhost';
FLUSH PRIVILEGES;
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` with your settings:
```env
# Database
DATABASE_URL=mysql+pymysql://attainment:1234@localhost:3306/co_po_attainment

# LLM Configuration
LLM_PROVIDER=gemini
LLM_API_KEY=your_google_gemini_api_key
LLM_MODEL=gemini-3.6-flash

# Embedding Model
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Mock mode (set to true to run offline without API key)
MOCK_MODE=false
```

---

## 🖥️ Running the Application

Start the FastAPI server:
```bash
source venv/bin/activate
uvicorn main:app --reload
```
Open your browser and navigate to:
**`http://127.0.0.1:8000`**

---

## 🧪 Testing

### Automated Unit Tests
The repository includes a comprehensive 52-test test suite covering preprocessing, embeddings, validators, parsers, and evaluation metrics:

```bash
source venv/bin/activate

# Run all unit tests
python -m pytest tests/ -v -k "not slow"

# Run all tests including model downloads
python -m pytest tests/ -v
```

---

## 📖 Step-by-Step Usage Guide

1. **Setup Tab**:
   - Create a Subject (e.g., Course Code `CS206`, Course Name `Data Structures`).
   - Add Course Outcomes (COs) and input their initial University Result $(a)$ and Internal Assessment $(b)$ levels.
   - Click **Load NBA Standard POs** to populate PO1 to PO11.
   - Add Program Specific Outcomes (PSOs) or click **Load Default PSOs**.
2. **AI Mapping Tab**:
   - Choose mapping method: **Hybrid (Recommended)**, **Embedding Only**, or **LLM Only**.
   - Click **Generate CO-PO Mapping**.
   - The interactive matrix renders with:
     - University Result $(a)$ & Internal Assessment $(b)$
     - Automatically computed **Total CO Attainment**
     - AI mapping levels (1, 2, 3, or `—`)
     - Live-calculated **PO / PSO Attainment** footer row.
   - Edit any $(a)$ or $(b)$ value directly in the matrix table cells to watch total and PO attainments recalculate dynamically!
   - Click on any matrix cell to inspect the side panel detailing similarity scores, Bloom's concepts, and Gemini reasoning.
3. **Review Tab**:
   - Approve, adjust, or reject individual AI-suggested mappings.
4. **Evaluation Tab**:
   - Upload your faculty reference Excel file in Setup.
   - Click **Run Evaluation** to benchmark Accuracy, Precision, Recall, Macro-F1, and Confusion Matrix.
5. **Export Tab**:
   - Export evaluation and attainment matrices into an Excel workbook.

---

## 📄 License

Academic Project — BE Final Year (2024–25).
Developed for automated Outcome-Based Education (OBE) and NBA accreditation workflow.