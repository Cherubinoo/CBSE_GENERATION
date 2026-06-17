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
