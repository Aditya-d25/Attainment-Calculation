# System Diagrams Implementation Plan — Outcome Studio

This document provides a comprehensive implementation plan and ready-to-render system diagrams tailored specifically to the **Outcome Studio (AI CO–PO/PSO Mapping & Attainment Platform)** codebase.

---

## 📑 1. Diagram Requirements & Scope

For engineering capstone projects, academic reports (SPPU / AICTE / NBA), and technical documentation, the system is represented across four distinct viewpoints:

| Category | Diagram Name | Purpose in Outcome Studio | Primary Code References |
| :--- | :--- | :--- | :--- |
| **Structural** | **1. System Architecture (Layered)** | Multi-tier view from UI to AI engine and DB | [main.py](file:///home/atharv/Documents/BE_Project/main.py), [database.py](file:///home/atharv/Documents/BE_Project/database.py) |
| **Structural** | **2. Component Diagram** | Inter-module contracts & service dependencies | [routers/](file:///home/atharv/Documents/BE_Project/routers), [services/](file:///home/atharv/Documents/BE_Project/services), [ai/](file:///home/atharv/Documents/BE_Project/ai) |
| **Structural** | **3. Entity-Relationship (ER) Diagram** | Database relational schema & cardinalities | [models.py](file:///home/atharv/Documents/BE_Project/models.py), [schema.sql](file:///home/atharv/Documents/BE_Project/schema.sql) |
| **Behavioral** | **4. Data Flow Diagram (DFD Level 0 & 1)** | Transformation of syllabus PDF to mapped matrix | [services/pdf_parser.py](file:///home/atharv/Documents/BE_Project/services/pdf_parser.py), [ai/mapper.py](file:///home/atharv/Documents/BE_Project/ai/mapper.py) |
| **Behavioral** | **5. Sequence Diagram (Hybrid AI Mapping)** | Detailed invocation order: Vector + LLM + Fallback | [ai/mapper.py](file:///home/atharv/Documents/BE_Project/ai/mapper.py), [ai/llm_reasoner.py](file:///home/atharv/Documents/BE_Project/ai/llm_reasoner.py) |
| **Behavioral** | **6. Activity / Workflow Diagram** | End-to-end faculty-in-the-loop lifecycle | [routers/mapping.py](file:///home/atharv/Documents/BE_Project/routers/mapping.py), [frontend/static/app.js](file:///home/atharv/Documents/BE_Project/frontend/static/app.js) |
| **Physical** | **7. Deployment Diagram** | Server runtime, local vector store, external LLMs | [server.py](file:///home/atharv/Documents/BE_Project/server.py), `requirements.txt` |

---

## 🛠️ 2. Step-by-Step Implementation Plan

```mermaid
flowchart TD
    A["Phase 1: Architecture & Structural Baseline"] --> B["Phase 2: Data Flow & Database Modelling"]
    B --> C["Phase 3: Dynamic & Behavioral Sequences"]
    C --> D["Phase 4: Export, Review & Report Integration"]

    A1["Extract Subsystems & APIs"] --> A
    B1["Model Tables & Foreign Keys"] --> B
    C1["Trace AI Pipeline & Fallbacks"] --> C
    D1["Generate SVGs / PNGs for Report"] --> D
```

### Phase 1: High-Level Structural Modeling
- [x] Analyze codebase structure: FastAPI routers, services, AI coordinator, database layer.
- [x] Construct **High-Level Tiered Architecture**.
- [x] Construct **Component Interconnection Diagram**.

### Phase 2: Data & Storage Modeling
- [x] Map relational entities from [models.py](file:///home/atharv/Documents/BE_Project/models.py): `OutcomeFramework`, `Subject`, `CourseOutcome`, `AIMappingResult`, `MappingEvaluation`.
- [x] Generate **Entity-Relationship (ER) Diagram**.
- [x] Construct **Data Flow Diagram (Level 0 Context & Level 1 Functional)**.

### Phase 3: Process & Behavioral Modeling
- [x] Trace hybrid mapping flow: Preprocessing -> TF-IDF/ChromaDB -> Gemini/Groq LLM -> Accreditation Fallback -> Validation.
- [x] Trace Faculty Calibration Loop: Cell inspection, manual override, historical few-shot caching.
- [x] Generate **Sequence Diagram** and **Activity Diagram**.

### Phase 4: Output & Report Formatting
- Export Mermaid diagrams to high-resolution vector SVGs or PNGs for the BE Project Report / Thesis using Mermaid Live Editor or Mermaid CLI.

---

## 📐 3. System Diagrams Specification (Ready-to-Use)

### Diagram 1: Layered System Architecture
Shows the presentation layer, REST API gateways, hybrid AI engine, storage, and third-party AI providers.

```mermaid
graph TB
    subgraph Presentation_Layer["Presentation Layer (Client-Side)"]
        UI["Glassmorphic Web Dashboard<br/>(Vanilla HTML5 / CSS3 / ES6 JavaScript)"]
        AuthUI["Login Gateway<br/>(Google OAuth2 / Guest Mode)"]
        MatrixGrid["Interactive Matrix View<br/>(Cell Inspector & Level Override Modal)"]
    end

    subgraph API_Layer["Application & API Layer (FastAPI Backend)"]
        RouterAuth["Auth Router<br/>routers/auth.py"]
        RouterFrameworks["Frameworks Router<br/>routers/frameworks.py"]
        RouterSubjects["Subjects Router<br/>routers/subjects.py"]
        RouterPDF["PDF Router<br/>routers/pdf.py"]
        RouterMapping["Mapping Router<br/>routers/mapping.py"]
        RouterExcel["Excel Router<br/>routers/excel.py"]
    end

    subgraph Service_AI_Layer["Business Logic & Hybrid AI Engine"]
        PDFParser["PDF Parser Service<br/>Regex & PyPDF Extraction"]
        MappingService["Mapping Service<br/>Orchestration & State Management"]
        ExcelExporter["Excel Exporter<br/>OpenPyXL Multi-Sheet Generator"]

        subgraph AI_Pipeline["Hybrid AI Pipeline (ai/)"]
            Preprocessor["Text Preprocessor<br/>Bloom's Taxonomy Verbs"]
            Embeddings["Embeddings Engine<br/>TF-IDF & Vector Similarity"]
            CandidateFilter["Candidate Generator<br/>Threshold + Top-K Filtering"]
            LLMReasoner["LLM Reasoner<br/>Gemini / Groq with Rate-Limiting"]
            FallbackEngine["Accreditation Rule Engine<br/>Deterministic Fallback"]
            Validator["Mapping Validator<br/>Outlier & Bounds Check"]
        end
    end

    subgraph Data_Layer["Data & Persistence Layer"]
        RDBMS[("Relational Database<br/>SQLite / MySQL via SQLAlchemy")]
        VectorStore[("ChromaDB Vector Store<br/>chroma_db/")]
        FileStore["Uploads & Documents<br/>uploads/"]
    end

    subgraph External_APIs["External Cloud Services"]
        GeminiAPI["Google Gemini Pro / Flash API"]
        GroqAPI["Groq LLaMA-3 Cloud API"]
        GoogleOAuth["Google Identity Services"]
    end

    %% Connections
    UI --> RouterAuth & RouterFrameworks & RouterSubjects & RouterPDF & RouterMapping & RouterExcel
    RouterAuth --> GoogleOAuth
    RouterPDF --> PDFParser
    RouterExcel --> ExcelExporter
    RouterMapping --> MappingService
    MappingService --> AI_Pipeline

    AI_Pipeline --> GeminiAPI & GroqAPI
    AI_Pipeline -.-> FallbackEngine
    AI_Pipeline --> VectorStore

    MappingService --> RDBMS
    RouterFrameworks & RouterSubjects --> RDBMS
    RouterPDF --> FileStore
```

---

### Diagram 2: Data Flow Diagram (DFD Level 0 & Level 1)

#### DFD Level 0 (Context Diagram)
```mermaid
flowchart LR
    Faculty(["Faculty / HOD"])
    System[["Outcome Studio<br/>CO-PO Mapping Agent"]]
    ExtLLM[["External LLMs<br/>(Gemini / Groq)"]]
    Database[("System Database")]

    Faculty -->|"Uploads Syllabus PDF / Edits COs / Reviews Cells"| System
    System -->|"Generates Mapping Matrix, Explanations & XLSX Reports"| Faculty

    System <-->|"Prompts & Contextual Reasoning"| ExtLLM
    System <-->|"Read / Write Frameworks, Matrices & Evaluations"| Database
```

#### DFD Level 1 (Functional Decomposition)
```mermaid
flowchart TD
    User(["Faculty / HOD"])

    subgraph DFD1["Outcome Studio Level 1 DFD"]
        P1["1.0<br/>Parse Syllabus PDF"]
        P2["2.0<br/>Manage Frameworks & Outcomes"]
        P3["3.0<br/>Extract Features & Compute Similarity"]
        P4["4.0<br/>Execute Hybrid Reasoning"]
        P5["5.0<br/>Faculty Review & Calibration"]
        P6["6.0<br/>Generate Excel Report"]

        D1[("D1: Syllabus Files")]
        D2[("D2: Outcome Frameworks & Subjects")]
        D3[("D3: AI Mapping Results & Calibration")]
        D4[("D4: Evaluated Reports")]
    end

    User -->|"Uploads Syllabus"| P1
    P1 -->|"Extracts COs & POs"| P2
    P1 -->|"Saves original PDF"| D1
    P2 <-->|"Stores Framework, Subject, CO definitions"| D2

    D2 -->|"CO & PO Text Pairs"| P3
    P3 -->|"Similarity Matrix & Candidate Pairs"| P4
    P4 -->|"Store AI Levels, Confidence & Justifications"| D3

    D3 -->|"Initial Matrix"| P5
    User -->|"Review Cell / Overwrite (0-3)"| P5
    P5 -->|"Persist Overrides & Notes"| D3

    D2 & D3 -->|"Final Matrix & Explanations"| P6
    P6 -->|"Download .xlsx file"| User
    P6 -->|"Save export record"| D4
```

---

### Diagram 3: Sequence Diagram — Hybrid AI Mapping & Fallback Pipeline
Illustrates the exact lifecycle from when faculty clicks "Generate Matrix" to database persistence.

```mermaid
sequenceDiagram
    autonumber
    actor Faculty as Faculty User
    participant Frontend as Frontend (app.js)
    participant Router as Mapping Router (mapping.py)
    participant Service as MappingService
    participant Pre as Preprocessor
    participant Embed as Embeddings (TF-IDF/Vector)
    participant LLM as LLM Reasoner (Gemini/Groq)
    participant Rule as Fallback Engine
    participant Val as Validator
    participant DB as SQLite / MySQL DB

    Faculty->>Frontend: Clicks "Generate Mapping Matrix"
    Frontend->>Router: POST /api/mapping/generate (subject_id, method="hybrid")
    Router->>Service: generate_subject_mapping(subject_id, method)
    Service->>DB: Fetch COs and linked Framework POs/PSOs
    DB-->>Service: Return Outcomes List

    Service->>Pre: preprocess_co() & preprocess_po() (Extract Bloom verbs)
    Pre-->>Service: Enhanced token representations

    Service->>Embed: compute_similarity_matrix(enhanced_co, enhanced_po)
    Embed-->>Service: Cosine Similarity Scores [0.0 - 1.0]

    Service->>Service: Filter Candidate Pairs (sim_score >= 0.12 or Core POs)

    alt External LLM Available (Quota Valid)
        Service->>LLM: evaluate_candidates_batch(candidates, few_shot_history)
        LLM-->>Service: Mapping Levels (0-3), Confidence, Reasoning, Evidence
    else Quota Exceeded / Offline / Error
        Service->>Rule: deterministic_accreditation_fallback()
        Rule-->>Service: Rule-based Levels & Pedagogical Justifications
    end

    Service->>Val: validate_mappings(results)
    Val-->>Service: Validated & Constrained Results

    Service->>DB: Bulk insert/update AIMappingResult records
    DB-->>Service: Confirm persistence

    Service-->>Router: Mapping Complete Response
    Router-->>Frontend: JSON Matrix Data (cells, confidence, reasoning)
    Frontend-->>Faculty: Render Interactive Glassmorphism Matrix
```

---

### Diagram 4: Entity-Relationship (ER) Diagram
Reflects the exact database schema from [models.py](file:///home/atharv/Documents/BE_Project/models.py).

```mermaid
erDiagram
    OUTCOME_FRAMEWORK ||--o{ FRAMEWORK_OUTCOME : contains
    OUTCOME_FRAMEWORK ||--o{ SUBJECT : standardizes
    SUBJECT ||--o{ COURSE_OUTCOME : defines
    SUBJECT ||--o{ PROGRAM_OUTCOME : associates
    SUBJECT ||--o{ PROGRAM_SPECIFIC_OUTCOME : associates
    SUBJECT ||--o{ AI_MAPPING_RESULT : maps
    SUBJECT ||--o{ REFERENCE_MAPPING_ENTRY : benchmarks
    SUBJECT ||--o{ MAPPING_EVALUATION : evaluates
    COURSE_OUTCOME ||--o{ AI_MAPPING_RESULT : targets

    OUTCOME_FRAMEWORK {
        int id PK
        string name UK
        string department
        text description
        datetime created_at
    }

    FRAMEWORK_OUTCOME {
        int id PK
        int framework_id FK
        string outcome_code
        string outcome_type "PO / PSO"
        text description
        datetime created_at
    }

    SUBJECT {
        int id PK
        int framework_id FK
        string course_code UK
        string course_name
        string year "FE/SE/TE/BE"
        string semester
        string division
        string academic_year
        boolean theory_enabled
        datetime created_at
    }

    COURSE_OUTCOME {
        int id PK
        int subject_id FK
        string co_code
        text description
        float univ_attainment
        float internal_attainment
        datetime created_at
    }

    AI_MAPPING_RESULT {
        int id PK
        int subject_id FK
        int co_id FK
        string co_code
        int po_pso_id
        string po_pso_code
        string po_pso_type "PO / PSO"
        int mapping_level "0 to 3"
        float confidence
        float similarity_score
        text reason
        text evidence
        string method "hybrid / embedding / llm"
        string faculty_decision "pending/accepted/edited"
        int final_mapping_level
        text faculty_notes
        datetime reviewed_at
    }

    MAPPING_EVALUATION {
        int id PK
        int subject_id FK
        string method
        float accuracy
        float precision_macro
        float recall_macro
        float f1_macro
        float agreement_percentage
        text confusion_matrix
        text classification_report
    }

    DOCUMENT {
        int id PK
        int subject_id FK
        string filename
        string file_path
        string doc_type
        datetime created_at
    }
```

---

### Diagram 5: Activity / Workflow Diagram (Faculty-in-the-Loop)
Shows the complete operational lifecycle from syllabus ingestion to accreditation export.

```mermaid
stateDiagram-v2
    [*] --> IngestionChoice: Faculty logs in

    state IngestionChoice <<choice>>
    IngestionChoice --> UploadPDF: Drag & Drop University Syllabus PDF
    IngestionChoice --> ManualEntry: Select Pre-configured Framework

    UploadPDF --> ParsePDF: Regex & PyPDF Extraction
    ParsePDF --> ReviewOutcomes: Auto-populate POs, PSOs & COs
    ManualEntry --> ReviewOutcomes: Select Subject

    ReviewOutcomes --> TriggerMapping: Verify Bloom's Taxonomy & Descriptions
    TriggerMapping --> HybridAI: Execute Hybrid Mapping Engine

    state HybridAI {
        [*] --> TextPreprocess
        TextPreprocess --> VectorSimilarity: TF-IDF & Cosine Distance
        VectorSimilarity --> CandidateFilter: Top-K & Core PO Thresholding
        CandidateFilter --> ContextualReasoning: Gemini / Groq LLM API
        ContextualReasoning --> ValidationEngine: Check Bound & Uniformity Rules
        ValidationEngine --> [*]
    }

    HybridAI --> RenderMatrix: Display Color-Coded Matrix (Levels 0-3)

    state ReviewLoop {
        RenderMatrix --> CellClick: Click cell to inspect
        CellClick --> ViewJustification: Show reasoning, confidence & evidence
        ViewJustification --> OverrideDecision: Double click to edit?
        OverrideDecision --> SaveOverride: Set Level (0-3) + Enter Faculty Notes
        SaveOverride --> RenderMatrix: Update final matrix
    }

    RenderMatrix --> ExportChoice: Matrix Finalized
    ExportChoice --> ExportExcel: Generate Multi-tab .xlsx Report
    ExportChoice --> RunEvaluation: Compare against Reference Benchmarks

    ExportExcel --> [*]
    RunEvaluation --> [*]
```

---

### Diagram 6: Deployment & Infrastructure Diagram
Shows runtime processes, networking, file storage, and external integrations.

```mermaid
graph TB
    subgraph Client_Device["Client Device (Faculty / Admin PC)"]
        Browser["Modern Web Browser<br/>(Chrome / Firefox / Edge / Safari)"]
    end

    subgraph Host_Server["Application Server (Local / Linux Host)"]
        direction TB
        ReverseProxy["Uvicorn ASGI Server<br/>Port 8000 (CORS Enabled)"]

        subgraph Python_Environment["Python 3.10+ Virtual Environment"]
            FastAPIApp["FastAPI Core Application<br/>(main.py)"]
            Jinja2["Jinja2 Template Engine"]
            PyPDFEngine["PyPDF / Regex Engine"]
            MLPipeline["Scikit-Learn TF-IDF & ChromaDB Client"]
            ReportGen["OpenPyXL XLSX Engine"]
        end

        subgraph Local_Storage["Local File Storage"]
            SQLiteDB[("SQLite Database<br/>test.db")]
            UploadDir["Uploaded Syllabi PDFs<br/>uploads/"]
            ChromaDir["ChromaDB Vector Store<br/>chroma_db/"]
        end
    end

    subgraph External_Cloud["External Cloud APIs"]
        GoogleCloud["Google Gemini AI API<br/>(Generative Language API)"]
        GroqCloud["Groq Cloud API<br/>(LLaMA-3 Inference)"]
        OAuthProvider["Google OAuth 2.0 Provider"]
    end

    Browser <-->|"HTTPS / HTTP (REST & Static Assets)"| ReverseProxy
    ReverseProxy --> FastAPIApp
    FastAPIApp --> Jinja2
    FastAPIApp --> PyPDFEngine
    FastAPIApp --> MLPipeline
    FastAPIApp --> ReportGen

    FastAPIApp <-->|"SQLAlchemy ORM"| SQLiteDB
    PyPDFEngine <-->|"Read / Write"| UploadDir
    MLPipeline <-->|"Local Embeddings Cache"| ChromaDir

    MLPipeline <-->|"REST API (API Key Auth)"| GoogleCloud
    MLPipeline <-->|"REST API (Fallback Inference)"| GroqCloud
    FastAPIApp <-->|"OAuth2 Exchange"| OAuthProvider
```

---

## 🚀 4. How to Use & Export These Diagrams

1. **In Antigravity IDE / Markdown Viewers**: All code blocks above use native GitHub Flavored Markdown `mermaid` syntax, rendering automatically.
2. **In Draw.io / Diagrams.net**: Open Draw.io -> Click `Arrange` -> `Insert` -> `Advanced` -> `Mermaid` -> Paste the code block.
3. **Mermaid Live Editor**: Visit [mermaid.live](https://mermaid.live), paste any diagram block, and export directly as high-resolution PNG, SVG, or PDF for your project report.
4. **Command Line Generation**: Run `npx -y @mermaid-js/mermaid-cli -i system_diagrams_implementation_plan.md -o output/` to batch-convert all diagrams into standalone vector graphics.
