import os
import uuid
from werkzeug.utils import secure_filename
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('APP')

def generate_exam_pattern(class_level, subjects, exam_type, chapters, file, upload_folder, allowed_extensions):
    """
    Generate an exam pattern, save the uploaded file, and return the result.
    Subjects is a list of subjects, chapters is a flat list of subject:chapter strings.
    Returns a dictionary with success status, filename, filepath, and error (if any).
    """
    try:
        if not file or not file.filename:
            logger.warning("No file provided for exam pattern")
            return {'success': False, 'error': 'Exam pattern file is required'}
        # Validate inputs
        if not all([class_level, subjects, exam_type, chapters]):
            return {'success': False, 'error': 'Class, subjects, exam type, and chapters are required'}
        # Handle file upload
        ext = file.filename.rsplit('.', 1)[-1].lower()
        if ext not in allowed_extensions:
            logger.warning(f"Unsupported file type: {ext}")
            return {'success': False, 'error': f'Unsupported file type: {ext}. Allowed: {", ".join(allowed_extensions)}'}
        if file.content_length > 10 * 1024 * 1024:
            logger.warning("File size exceeds 10MB limit")
            return {'success': False, 'error': 'File size exceeds 10MB limit'}
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        logger.info(f"Exam pattern file saved: {filepath}")
        # Log the exam pattern creation
        logger.info(f"Generated exam pattern: class_level={class_level}, subjects={subjects}, exam_type={exam_type}, chapters={chapters}")
        return {
            'success': True,
            'filename': filename,
            'filepath': filepath
        }
    except Exception as e:
        logger.exception(f"Error generating exam pattern: {str(e)}")
        return {'success': False, 'error': str(e)}