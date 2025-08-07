from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, DuplicateKeyError
import logging

# Set up logging (consistent with app.py)
logger = logging.getLogger('APP')

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['question_generator']

def store_to_mongo(metadata, text, embedding, collection_name=None):
    """
    Store the document text and its embedding into MongoDB.

    Args:
        metadata (dict): Includes class, subject, book, chapter_type, filename, and optionally chapter.
        text (str): Extracted OCR text.
        embedding (numpy.ndarray or list): Sentence embedding vector (optional).
        collection_name (str, optional): Name of the MongoDB collection (e.g., class10_mathematics).
                                        If None, derived from metadata['class'] and metadata['subject'].

    Returns:
        bool: True if stored successfully, False otherwise.
    """
    try:
        # Validate metadata
        required_keys = {'class', 'subject', 'book', 'chapter_type', 'filename'}
        if not all(key in metadata for key in required_keys):
            logger.error(f"Missing required metadata keys: {required_keys - set(metadata.keys())}")
            return False

        # Determine collection name
        if collection_name is None:
            collection_name = f"class{metadata['class']}_{metadata['subject'].lower().replace(' ', '_')}"
        collection = db[collection_name]

        # Create unique index on filename to prevent duplicates
        collection.create_index('filename', unique=True)

        # Convert embedding to list if it's a NumPy array
        embedding_list = embedding.tolist() if hasattr(embedding, 'tolist') else embedding

        # Build document
        document = {
            "filename": metadata["filename"],
            "class": metadata["class"],
            "subject": metadata["subject"],
            "book": metadata["book"],
            "chapter": metadata.get("chapter", "Unknown"),
            "chapter_type": metadata["chapter_type"],
            "text": text,
            "embedding": embedding_list if embedding is not None else []
        }

        result = collection.insert_one(document)
        logger.info(f"Stored in MongoDB → Collection: {collection_name}, _id: {result.inserted_id}, filename: {metadata['filename']}")
        return True
    except ConnectionFailure as e:
        logger.error(f"MongoDB connection failed: {e}")
        return False
    except DuplicateKeyError:
        logger.error(f"Duplicate document in {collection_name}: {metadata['filename']}")
        return False
    except Exception as e:
        logger.error(f"MongoDB insert failed: {e}")
        return False