import os
import logging
import mysql.connector
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Logging setup (aligned with app.py)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('SYNC_CONTENT')

# MySQL Database Configuration (from app.py)
mysql_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DB', 'education_db'),
    'connect_timeout': 10
}

# MongoDB Configuration (from app.py, read-only)
mongo_client = MongoClient('mongodb://localhost:27017/')
mongo_db = mongo_client['question_generator']

# File path configuration (from app.py)
UPLOAD_FOLDER = 'static/uploads'

def get_db_connection():
    """Establish MySQL connection."""
    try:
        conn = mysql.connector.connect(**mysql_config)
        logger.info("Successfully connected to MySQL database")
        return conn
    except mysql.connector.Error as e:
        logger.error(f"Failed to connect to MySQL: {str(e)}")
        raise

def check_table_schema(cursor):
    """Check the content table schema for duplicate class columns."""
    cursor.execute("DESCRIBE content")
    columns = [row[0] for row in cursor.fetchall()]
    logger.info(f"Content table columns: {columns}")
    class_columns = [col for col in columns if col.lower().startswith('class')]
    if len(class_columns) > 1:
        logger.warning(f"Multiple class-related columns detected: {class_columns}. This may cause issues. Consider dropping extra columns.")
    elif 'class' not in class_columns:
        logger.error("No 'class' column found in content table.")
        raise ValueError("Content table missing required 'class' column")
    return class_columns

def get_mongo_collections():
    """Get all collections in MongoDB that match the pattern class*_*, excluding exam_pattern_combined."""
    collections = mongo_db.list_collection_names()
    relevant_collections = [
        col for col in collections 
        if col.startswith('class') and '_' in col and col != 'exam_pattern_combined'
    ]
    logger.info(f"Found {len(relevant_collections)} relevant collections: {relevant_collections}")
    return relevant_collections

def check_mysql_for_mongo_id(mongo_id, cursor):
    """Check if a MongoDB document ID exists in the MySQL content table."""
    cursor.execute(
        "SELECT COUNT(*) FROM content WHERE mongo_id = %s",
        (str(mongo_id),)
    )
    count = cursor.fetchone()[0]
    return count > 0

def validate_class(class_value):
    """Validate the class field to ensure it's a non-empty string suitable for MySQL."""
    if not class_value:
        logger.warning("Class field is missing or empty. Using 'General'.")
        return 'General'
    class_str = str(class_value).strip()
    if len(class_str) > 10:
        logger.warning(f"Class value '{class_str}' exceeds 10 characters. Truncating.")
        class_str = class_str[:10]
    if not class_str:
        logger.warning("Class value is empty after stripping. Using 'General'.")
        return 'General'
    logger.debug(f"Validated class value: {class_str}")
    return class_str

def insert_into_mysql(doc, cursor, conn):
    """Insert a MongoDB document's metadata into the MySQL content table."""
    filename = doc.get('filename')
    filepath = os.path.join(UPLOAD_FOLDER, filename) if filename else None
    
    # Map MongoDB fields to MySQL content table fields
    class_value = validate_class(doc.get('class', ''))
    subject = doc.get('subject', 'Unknown').strip()
    book_name = doc.get('book', 'Unknown').strip()
    chapter = doc.get('chapter', None)
    resource_type = doc.get('chapter_type', 'Unknown').strip()
    sub_subject = doc.get('sub_subject', None)
    mongo_id = str(doc['_id'])

    # Log the class value for debugging
    logger.debug(f"Processing document with mongo_id={mongo_id}, class={class_value}, subject={subject}")

    # Ensure NOT NULL fields have valid values
    if not filename:
        logger.warning(f"No filename provided for mongo_id={mongo_id}. Using 'unknown.pdf'.")
        filename = 'unknown.pdf'
        filepath = None
    if not filepath:
        logger.warning(f"No filepath provided for mongo_id={mongo_id}. Using 'unknown'.")
        filepath = 'unknown'

    try:
        cursor.execute(
            """
            INSERT INTO content (class, subject, book_name, chapter, resource_type, filename, filepath, mongo_id, sub_subject)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                class_value,
                subject[:100],  # Fit VARCHAR(100)
                book_name[:255],  # Fit VARCHAR(255)
                chapter[:255] if chapter else None,  # Fit VARCHAR(255)
                resource_type[:100],  # Fit VARCHAR(100)
                filename[:255],  # Fit VARCHAR(255)
                filepath[:255],  # Fit VARCHAR(255)
                mongo_id,
                sub_subject[:100] if sub_subject else None  # Fit VARCHAR(100)
            )
        )
        conn.commit()
        content_id = cursor.lastrowid
        logger.info(f"Inserted into MySQL: content_id={content_id}, mongo_id={mongo_id}, class={class_value}, filename={filename}")
        return content_id
    except mysql.connector.Error as e:
        logger.error(f"Failed to insert into MySQL for mongo_id={mongo_id}: {str(e)}")
        return None

def sync_content():
    """Synchronize MongoDB content to MySQL content table without modifying MongoDB."""
    try:
        # Connect to MySQL
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check content table schema
        class_columns = check_table_schema(cursor)
        logger.info(f"Class-related columns: {class_columns}")

        # Get MongoDB collections
        collections = get_mongo_collections()
        if not collections:
            logger.warning("No relevant MongoDB collections found.")
            cursor.close()
            conn.close()
            return

        total_inserted = 0
        for collection_name in collections:
            logger.info(f"Processing collection: {collection_name}")
            collection = mongo_db[collection_name]
            documents = collection.find()

            for doc in documents:
                mongo_id = doc.get('_id')
                if not mongo_id:
                    logger.warning(f"Document in {collection_name} has no _id. Skipping.")
                    continue

                # Check if mongo_id exists in MySQL
                if check_mysql_for_mongo_id(mongo_id, cursor):
                    logger.debug(f"Document with mongo_id={mongo_id} already exists in MySQL. Skipping.")
                    continue

                # Insert into MySQL
                content_id = insert_into_mysql(doc, cursor, conn)
                if content_id:
                    total_inserted += 1
                else:
                    logger.warning(f"Failed to insert document with mongo_id={mongo_id} into MySQL.")

        logger.info(f"Synchronization complete. Inserted {total_inserted} new records into MySQL.")
        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"Error during synchronization: {str(e)}")
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        raise

if __name__ == '__main__':
    try:
        sync_content()
        print("Synchronization completed successfully.")
    except Exception as e:
        print(f"Error: {str(e)}")