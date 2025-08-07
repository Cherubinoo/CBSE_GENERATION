import os
import tempfile
from pdf2image import convert_from_path
from pdf2image.exceptions import PDFPageCountError
from paddleocr import PaddleOCR
import numpy as np
from pathlib import Path
import sys
import json

# Set poppler path (Windows)
poppler_path = r"C:\poppler\Library\poppler-24.08.0\Library\bin"

# Initialize PaddleOCR
ocr = PaddleOCR(lang='en', use_angle_cls=False, use_gpu=False)

def extract_text_from_pdf(filepath):
    """
    Extract text from a PDF using OCR.
    """
    try:
        print(f"\n[DEBUG] Starting PDF processing for: {filepath}")
        print(f"[DEBUG] Using Poppler path: {poppler_path}")

        # Step 1: Convert PDF pages to images
        try:
            images = convert_from_path(filepath, poppler_path=poppler_path)
            if not images:
                print("[DEBUG] No images converted from PDF. Check PDF content or Poppler setup.")
                return None
            print(f"[DEBUG] Successfully converted {len(images)} pages to images.")
        except PDFPageCountError as e:
            print(f"[ERROR] PDF Page Count Error during convert_from_path: {e}")
            print(f"[ERROR] This often means the PDF is malformed or encrypted. File: {filepath}")
            return None
        except Exception as e:
            print(f"[ERROR] Unexpected error during convert_from_path: {e}. File: {filepath}")
            return None

        all_text = []

        for i, image in enumerate(images):
            temp_img_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_img:
                    temp_img_path = temp_img.name
                    image.save(temp_img_path, "PNG")
                print(f"[DEBUG] Saved page {i+1} to temporary image: {temp_img_path}")

                # OCR
                result = ocr.ocr(temp_img_path)
                print(f"[DEBUG] OCR processed page {i+1}. Result type: {type(result)}")

                if not result or not result[0]:
                    print(f"[DEBUG] No text detected by OCR on page {i+1}.")
                    continue

                # Flatten the structure if result is nested
                page_text_lines = []
                if isinstance(result[0], list):
                    for line in result[0]:
                        if isinstance(line, list) and len(line) > 1 and isinstance(line[1], tuple):
                            page_text_lines.append(line[1][0])
                        else:
                            print(f"[DEBUG] Unexpected OCR line format on page {i+1}: {line}")
                else:
                    print(f"[DEBUG] OCR result[0] is not a list. Type: {type(result[0])}")

                page_text = "\n".join(page_text_lines)
                if page_text:
                    all_text.append(page_text)
                    print(f"[DEBUG] Extracted text from page {i+1} (first 50 chars): '{page_text[:50]}'")
                else:
                    print(f"[DEBUG] No valid text lines extracted from page {i+1} despite OCR result.")

            except Exception as e:
                print(f"[ERROR] Error during processing of page {i+1}: {e}")
            finally:
                if temp_img_path and os.path.exists(temp_img_path):
                    os.remove(temp_img_path)
                    print(f"[DEBUG] Removed temporary image: {temp_img_path}")

        if not all_text:
            print("[DEBUG] No text extracted from any page after iterating all images.")
            return None

        final_output = "\n\n".join(all_text)
        print(f"[DEBUG] Successfully extracted total text length: {len(final_output)}")
        return final_output

    except Exception as e:
        print(f"[ERROR] Overall OCR process failed: {e}")
        return None

if __name__ == "__main__":
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