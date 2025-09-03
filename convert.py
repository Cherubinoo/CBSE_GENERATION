# convert.py
import os
import tempfile
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError
from paddleocr import PaddleOCR
import logging

# Logging setup (aligned with app.py)
logger = logging.getLogger('CONVERT')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# Set poppler path (Windows)
poppler_path = r"C:\poppler\Library\poppler-24.08.0\Library\bin"

# Initialize PaddleOCR
ocr = PaddleOCR(lang='en', use_angle_cls=False, use_gpu=False)

def extract_text_from_pdf(filepath):
    """
    Extract text from a PDF using OCR.
    """
    try:
        logger.info(f"Starting PDF processing for: {filepath}")
        logger.debug(f"Using Poppler path: {poppler_path}")

        # Step 1: Convert PDF pages to images
        try:
            images = convert_from_path(filepath, poppler_path=poppler_path)
            if not images:
                logger.warning("No images converted from PDF. Check PDF content or Poppler setup.")
                return None
            logger.info(f"Successfully converted {len(images)} pages to images.")
        except PDFPageCountError as e:
            logger.error(f"PDF Page Count Error during convert_from_path: {e}")
            logger.error(f"This often means the PDF is malformed or encrypted. File: {filepath}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during convert_from_path: {e}. File: {filepath}")
            return None

        all_text = []

        for i, image in enumerate(images):
            temp_img_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
                    temp_img_path = temp_img.name
                    image.save(temp_img_path, "PNG")
                logger.debug(f"Saved page {i+1} to temporary image: {temp_img_path}")

                # OCR
                result = ocr.ocr(temp_img_path)
                logger.debug(f"OCR processed page {i+1}. Result type: {type(result)}")

                if not result or not result[0]:
                    logger.debug(f"No text detected by OCR on page {i+1}.")
                    continue

                # Flatten the structure if result is nested
                page_text_lines = []
                if isinstance(result[0], list):
                    for line in result[0]:
                        if isinstance(line, list) and len(line) > 1 and isinstance(line[1], tuple):
                            page_text_lines.append(line[1][0])
                        else:
                            logger.debug(f"Unexpected OCR line format on page {i+1}: {line}")
                else:
                    logger.debug(f"OCR result[0] is not a list. Type: {type(result[0])}")

                page_text = "\n".join(page_text_lines)
                if page_text:
                    all_text.append(page_text)
                    logger.debug(f"Extracted text from page {i+1} (first 50 chars): '{page_text[:50]}'")
                else:
                    logger.debug(f"No valid text lines extracted from page {i+1} despite OCR result.")

            except Exception as e:
                logger.error(f"Error during processing of page {i+1}: {e}")
            finally:
                if temp_img_path and os.path.exists(temp_img_path):
                    try:
                        os.remove(temp_img_path)
                        logger.debug(f"Removed temporary image: {temp_img_path}")
                    except OSError as e:
                        logger.error(f"Failed to remove temporary image {temp_img_path}: {e}")

        if not all_text:
            logger.warning("No text extracted from any page after iterating all images.")
            return None

        final_output = "\n\n".join(all_text)
        logger.info(f"Successfully extracted total text length: {len(final_output)}")
        return final_output

    except Exception as e:
        logger.error(f"Overall OCR process failed: {e}")
        return None

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) != 2:
        print(json.dumps({"error": "Usage: python convert.py path_to_pdf"}))
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(json.dumps({"error": f"File not found: {filepath}"}))
        sys.exit(1)

    result = extract_text_from_pdf(filepath)
    if result:
        print(json.dumps({"text": result}))
    else:
        print(json.dumps({"error": "No text extracted"}))