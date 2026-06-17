# CBSE Question Paper Generator

An end-to-end Flask web application that helps schools digitize their curriculum content (textbooks, notes, syllabi) and automatically generate CBSE-style question papers using a locally hosted LLM (via Ollama). Admins upload chapter-wise study material, define custom exam patterns/blueprints, and the system generates a fully formatted question paper (DOCX + PDF) grounded strictly in the uploaded content.

## Overview

The application is built for school administrators/staff to:

1. **Digitize content** — Upload textbooks, notes, syllabi, and previous question papers (PDF, DOC/DOCX, TXT, or scanned images) for any class (1–12) and subject. Text is automatically extracted using OCR/document parsing.
2. **Define exam patterns** — Create reusable exam blueprints (unit test, slip test, pre-midterm, post-midterm, terminal exams, or custom types) by uploading a pattern/marking-scheme document and selecting the chapters to be covered.
3. **Generate question papers** — Pick a class, subject, exam pattern, chapters, and difficulty level (easy/medium/hard). The system feeds the relevant chapter content and the pattern's mark distribution into a local LLM (Ollama, `llama3`) to generate a complete, section-wise question paper, then exports it as a formatted `.docx` and converts it to `.pdf`.

It also includes basic staff management (Teachers/Admins/Support staff) and subject/resource-type administration.

## Key Features

- **Admin authentication** with a session-based login for all management routes.
- **Multi-format content ingestion**: PDF, DOC/DOCX, TXT, PNG/JPG/JPEG.
- **OCR text extraction** for scanned PDFs and images using PaddleOCR (English recognition model bundled locally), with `pdf2image`/Poppler used to rasterize PDF pages before OCR.
- **Dual-database architecture**:
  - **MySQL** stores structured/relational metadata — classes, subjects, sub-subjects, resource types, exam types, staff, content records, and exam pattern records.
  - **MongoDB** stores the actual extracted text content (per class+subject collections) and exam pattern documents, linked back to MySQL via stored Mongo ObjectIDs.
- **Class & subject management** with sensible CBSE defaults pre-seeded for classes 1–12 (English, Mathematics, Science, Social Studies, Hindi, Computer Science, Economics, Accountancy, Business Studies, etc.), plus sub-subject support for Science (Physics/Chemistry/Biology) and Social Studies (History/Geography/Civics/Economics).
- **Custom exam pattern builder** — define total marks and section-wise structure (e.g., "Section A: 10 questions of 1 mark each") by uploading a pattern document; the app parses it automatically using regex-based extraction.
- **AI-powered question generation** — uses a locally running Ollama LLM (`llama3`) to generate questions strictly from the uploaded chapter content, following the parsed mark distribution, section structure, and selected difficulty level.
- **Automatic document generation** — produces a formatted Word document (with school letterhead, class/subject/marks/time header) via `python-docx`, then converts it to PDF.
- **Staff management** — add, edit, view, and delete staff records (Teacher/Admin/Support roles).
- **REST-ish JSON endpoints** for dynamic frontend dropdowns (subjects, sub-subjects, chapters, book names, resource types, exam patterns) used to power cascading form selections in the UI.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Relational DB | MySQL (`mysql-connector-python`) |
| Document/content store | MongoDB (`pymongo`) |
| OCR | PaddleOCR (`en_PP-OCRv3_rec` model bundled) |
| PDF → image rendering | `pdf2image` + Poppler |
| Document generation | `python-docx` |
| DOCX → PDF conversion | `docx2pdf` (requires Microsoft Word / Windows COM, via `pythoncom`) |
| Question generation (LLM) | Ollama running `llama3` locally |
| Embeddings (optional/legacy) | `sentence-transformers` (`all-MiniLM-L6-v2`, cached locally) |
| Frontend | HTML, CSS, JavaScript, Jinja2 templates |

## Project Structure

CBSE_GENERATION/
├── app.py # Main Flask application — routes, DB init, content & exam pattern CRUD
├── run.py # Alternate/standalone entry point with embedded helper logic
│ and an auto-managed embedding microservice
├── utils.py # extract_text_from_file() — routes PDFs/images/docs/txt to the right parser
├── convert.py # PDF → image → OCR text extraction (PaddleOCR + Poppler)
├── store.py # Persists extracted content + metadata into MongoDB
├── generate_exam_pattern.py # Validates & saves uploaded exam pattern files, parses mark structure
├── store_exam_pattern.py # Persists exam pattern documents into MongoDB
├── question_generator.py # Core generator: builds the LLM prompt, calls Ollama, builds DOCX/PDF
├── generator.py # Earlier/alternate question-generation helper functions
├── sync_content_to_mysql.py # Utility script to reconcile/sync content records between MongoDB and MySQL
├── models/ # Local model assets
├── model_cache/ # Cached sentence-transformers embedding model (all-MiniLM-L6-v2)
├── en_PP-OCRv3_rec/ # Bundled PaddleOCR English recognition model
├── templates/ # Jinja2 HTML templates (admin dashboard, upload forms, exam pattern UI, etc.)
├── static/ # CSS, JS, uploaded files, and generated outputs
├── uploads/ # Raw uploaded source files
└── .gitignore


## Prerequisites

Before running the project, make sure you have:

- **Python 3.9+**
- **MySQL Server** running locally (or accessible) — the app auto-creates the required tables (`admins`, `subjects`, `exam_types`, `resource_types`, `content`, `exam_patterns`, `staff`) on first run.
- **MongoDB Server** running locally (default `mongodb://localhost:27017/`).
- **Ollama** installed and running locally, with the `llama3` model pulled (`ollama pull llama3`).
- **Poppler** installed and accessible (used by `pdf2image` for PDF rasterization before OCR). Note: the bundled `convert.py`/`run.py` code currently hardcodes a Windows Poppler path — update this for your OS/environment.
- **Microsoft Word** installed (Windows) if you intend to use the DOCX → PDF conversion path that relies on `docx2pdf`/`pythoncom`, since it automates Word via COM. On Linux/macOS you'll need to swap this for a different conversion approach (e.g., LibreOffice headless).

## Installation

1. **Clone the repository**
```bash
   git clone https://github.com/Cherubinoo/CBSE_GENERATION.git
   cd CBSE_GENERATION
```

2. **Create and activate a virtual environment**
```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
   The repo does not currently ship a `requirements.txt`. Based on the imports used across the codebase, install:
```bash
   pip install flask werkzeug python-dotenv mysql-connector-python pymongo \
               paddleocr paddlepaddle python-docx docx2pdf pdf2image \
               reportlab ollama requests sentence-transformers pywin32
```
   > `pywin32` (which provides `pythoncom`) and `docx2pdf` are Windows-only requirements needed for the DOCX → PDF conversion step.

4. **Set up environment variables**
   Create a `.env` file in the project root:
```env
   SECRET_KEY=your_secret_key_here
   MYSQL_HOST=localhost
   MYSQL_USER=root
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_DB=education_db
   MONGODB_URI=mongodb://localhost:27017/
   EMBEDDING_SERVICE_URL=http://localhost:5001/generate_embedding
   OLLAMA_MODEL=llama3
```

5. **Create the MySQL database** (the app creates tables automatically, but the database itself must exist):
```sql
   CREATE DATABASE education_db;
```

6. **Start Ollama** (in a separate terminal) and make sure the model is available:
```bash
   ollama serve
   ollama pull llama3
```

7. **Run the application**
```bash
   python app.py
```
   The app will be available at `http://localhost:5000`.

## Default Admin Credentials

On first run, a default admin account is automatically created:
Username: admin
Password: admin123


**Change this immediately** if deploying anywhere beyond local development — credentials are currently stored and checked as plain text, which is not safe for production use.

## Usage Walkthrough

1. **Log in** as admin at `/admin_login`.
2. **Upload content** (`/upload_content`): select class, subject (and sub-subject if applicable), book name, chapter, and resource type, then upload the source file. Text is extracted automatically and stored in MongoDB, with metadata in MySQL.
3. **Create an exam pattern** (`/create_exam_pattern`): choose class, subject(s), exam type, the chapters to be covered, and upload a pattern/marking-scheme document describing total marks and section structure.
4. **Generate a question paper**: select a pattern, chapters, and difficulty level. The system retrieves the relevant chapter text from MongoDB, builds a structured prompt (including section breakdown and per-chapter mark allocation), sends it to the local Ollama LLM, and returns a generated paper.
5. **Download the result** as a formatted DOCX or converted PDF, ready to print or share.

## Notes & Limitations

- **Windows-centric pieces**: `docx2pdf` + `pythoncom` (Word automation) and the hardcoded Poppler path mean the DOCX→PDF pipeline currently targets Windows. For Linux/macOS deployments, consider swapping in a LibreOffice (`soffice --headless --convert-to pdf`) based conversion.
- **OCR accuracy**: scanned/handwritten content quality depends entirely on PaddleOCR's English recognition model; clean, well-scanned typed text will extract far more reliably than handwriting or low-resolution scans.
- **LLM grounding**: question generation is explicitly prompted to stay within the uploaded chapter content only, but as with any LLM-based generation, output should be reviewed by a teacher/subject expert before being used in an actual exam.
- **`run.py` vs `app.py`**: the repo contains two overlapping entry points. `app.py` is the modular, currently maintained version (using `utils.py`, `store.py`, `generate_exam_pattern.py`, `store_exam_pattern.py`, and `question_generator.py`). `run.py` is a more monolithic alternate version that also manages a separate embedding microservice — use `app.py` unless you specifically need the embedding-service workflow.
- **Two question-generation modules**: `question_generator.py` (used by `app.py`) is the current generation pipeline; `generator.py` contains earlier helper functions for a similar purpose.

## Roadmap Ideas

- Add a `requirements.txt` / `pyproject.toml` for reproducible installs.
- Replace plaintext admin password storage/checks with hashed passwords.
- Cross-platform DOCX → PDF conversion (LibreOffice-based) to remove the Windows/MS Word dependency.
- Add automated tests and a CI pipeline.
- Add a proper `LICENSE` file.

## Contributing

Contributions, issues, and feature requests are welcome. Feel free to open an issue or submit a pull request.

## License

No license has been specified for this repository yet. Consider adding one (e.g., MIT) if you intend others to reuse this code.
A few honest notes since I read straight from the source: there's currently no requirements.txt, LICENSE, or repo description on GitHub, and the admin credentials/password handling are stored in plain text — I flagged both in the README rather than glossing over them. Feel free to tell me to trim the "Notes & Limitations" or "Roadmap" sections if you'd rather keep it leaner.



Claude Fable 5 is cur


## Prerequisites

Before running the project, make sure you have:

- **Python 3.9+**
- **MySQL Server** running locally (or accessible) — the app auto-creates the required tables (`admins`, `subjects`, `exam_types`, `resource_types`, `content`, `exam_patterns`, `staff`) on first run.
- **MongoDB Server** running locally (default `mongodb://localhost:27017/`).
- **Ollama** installed and running locally, with the `llama3` model pulled (`ollama pull llama3`).
- **Poppler** installed and accessible (used by `pdf2image` for PDF rasterization before OCR). Note: the bundled `convert.py`/`run.py` code currently hardcodes a Windows Poppler path — update this for your OS/environment.
- **Microsoft Word** installed (Windows) if you intend to use the DOCX → PDF conversion path that relies on `docx2pdf`/`pythoncom`, since it automates Word via COM. On Linux/macOS you'll need to swap this for a different conversion approach (e.g., LibreOffice headless).

## Installation

1. **Clone the repository**
```bash
   git clone https://github.com/Cherubinoo/CBSE_GENERATION.git
   cd CBSE_GENERATION
```

2. **Create and activate a virtual environment**
```bash
   python -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
   The repo does not currently ship a `requirements.txt`. Based on the imports used across the codebase, install:
```bash
   pip install flask werkzeug python-dotenv mysql-connector-python pymongo \
               paddleocr paddlepaddle python-docx docx2pdf pdf2image \
               reportlab ollama requests sentence-transformers pywin32
```
   > `pywin32` (which provides `pythoncom`) and `docx2pdf` are Windows-only requirements needed for the DOCX → PDF conversion step.

4. **Set up environment variables**
   Create a `.env` file in the project root:
```env
   SECRET_KEY=your_secret_key_here
   MYSQL_HOST=localhost
   MYSQL_USER=root
   MYSQL_PASSWORD=your_mysql_password
   MYSQL_DB=education_db
   MONGODB_URI=mongodb://localhost:27017/
   EMBEDDING_SERVICE_URL=http://localhost:5001/generate_embedding
   OLLAMA_MODEL=llama3
```

5. **Create the MySQL database** (the app creates tables automatically, but the database itself must exist):
```sql
   CREATE DATABASE education_db;
```

6. **Start Ollama** (in a separate terminal) and make sure the model is available:
```bash
   ollama serve
   ollama pull llama3
```

7. **Run the application**
```bash
   python app.py
```
   The app will be available at `http://localhost:5000`.

## Default Admin Credentials

On first run, a default admin account is automatically created:
