# File: utils.py
import logging
from docx import Document
from paddleocr import PaddleOCR
from convert import extract_text_from_pdf

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('APP')

# Initialize PaddleOCR
try:
    ocr = PaddleOCR(lang='en', use_angle_cls=False, use_gpu=False, show_log=False)
except Exception as e:
    logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
    ocr = None

def extract_text_from_file(filepath):
    """Extract text from various file types (PDF, images, TXT, DOC/DOCX). Returns extracted text as a string or None if extraction fails."""
    try:
        ext = filepath.rsplit('.', 1)[-1].lower()
        logger.info(f"Extracting text from file: {filepath}, type: {ext}")
        if ext == 'pdf':
            text = extract_text_from_pdf(filepath)
            if text:
                logger.info(f"Extracted text from PDF (length: {len(text)})")
            else:
                logger.warning("No text extracted from PDF")
            return text
        elif ext in ('png', 'jpg', 'jpeg'):
            try:
                result = ocr.ocr(filepath) if ocr else None
                if not result or not result[0]:
                    logger.info("No text detected by OCR in image")
                    return None
                page_text_lines = []
                if isinstance(result[0], list):
                    for line in result[0]:
                        if isinstance(line, list) and len(line) > 1 and isinstance(line[1], tuple):
                            page_text_lines.append(line[1][0])
                text = "\n".join(page_text_lines) if page_text_lines else None
                if text:
                    logger.info(f"Extracted text from image (length: {len(text)})")
                else:
                    logger.warning("No text extracted from image")
                return text
            except Exception as e:
                logger.error(f"Image OCR failed: {e}")
                return None
        elif ext == 'txt':
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    text = f.read()
                if text.strip():
                    logger.info(f"Extracted text from TXT (length: {len(text)})")
                    return text
                logger.warning("No text extracted from TXT")
                return None
            except Exception as e:
                logger.error(f"TXT file read failed: {e}")
                return None
        elif ext in ('doc', 'docx'):
            try:
                doc = Document(filepath)
                text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                if text.strip():
                    logger.info(f"Extracted text from DOC/DOCX (length: {len(text)})")
                    return text
                logger.warning("No text extracted from DOC/DOCX")
                return None
            except Exception as e:
                logger.error(f"DOC/DOCX file read failed for {filepath}: {e}")
                return None
        else:
            logger.warning(f"Unsupported file type: {ext}")
            return None
    except Exception as e:
        logger.error(f"Text extraction failed for {filepath}: {e}")
        return None