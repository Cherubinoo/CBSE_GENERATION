import logging
from datetime import datetime
from store import store_to_mongo
from utils import extract_text_from_file
from pymongo import MongoClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('APP')

def store_exam_pattern_to_mongo(filepath, class_level, subjects, exam_type, chapters, filename, sub_subject=None):
    """
    Extract text from the exam pattern file and store it in MongoDB with a combined collection name.
    Includes sub-subject in metadata if provided.
    Returns a dictionary with success status, document ID (if stored), and error (if any).
    """
    try:
        # Validate inputs
        if not all([filepath, class_level, subjects, exam_type, chapters, filename]):
            logger.warning("Missing required fields for storing exam pattern in MongoDB")
            return {'success': False, 'error': 'All fields (filepath, class_level, subjects, exam_type, chapters, filename) are required'}
        # Extract text from the file
        text = extract_text_from_file(filepath)
        if not text or not text.strip():
            logger.warning(f"No text extracted from file: {filepath}")
            return {'success': False, 'error': 'No text could be extracted from the provided file'}
        # Prepare metadata
        metadata = {
            "name": exam_type,
            "class_level": class_level,
            "subjects": subjects,
            "sub_subject": sub_subject if sub_subject else None,
            "exam_type": exam_type,
            "chapter_type": "Exam Pattern",
            "filename": filename,
            "chapters": chapters,
            "created_at": datetime.now().isoformat()
        }
        # Use a fixed collection name for combined exam patterns
        collection_name = "exam_pattern_combined"
        # Store in MongoDB
        mongo_client = MongoClient('mongodb://localhost:27017/')
        mongo_db = mongo_client['question_generator']
        collection = mongo_db[collection_name]
        # Insert document
        document = {
            "metadata": metadata,
            "text": text
        }
        result = collection.insert_one(document)
        logger.info(f"Successfully stored exam pattern in MongoDB: filename={filename}, collection={collection_name}, document_id={result.inserted_id}")
        return {'success': True, 'document_id': str(result.inserted_id)}
    except Exception as e:
        logger.exception(f"Error storing exam pattern in MongoDB: {str(e)}")
        return {'success': False, 'error': str(e)}