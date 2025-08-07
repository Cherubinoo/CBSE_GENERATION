from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid
import logging
import mysql.connector
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from paddleocr import PaddleOCR
from docx import Document
from convert import extract_text_from_pdf
from store import store_to_mongo

# Load environment variables
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key_here')

# Config
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['OUTPUT_FOLDER'] = 'static/outputs'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'txt'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('APP')

# MySQL Database Connection
mysql_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DB', 'education_db'),
    'connect_timeout': 10
}

def get_db_connection():
    return mysql.connector.connect(**mysql_config)

# MongoDB Connections (only for question_generator)
mongo_client = MongoClient('mongodb://localhost:27017/')
mongo_question_db = mongo_client['question_generator']

# Initialize PaddleOCR
try:
    ocr = PaddleOCR(lang='en', use_angle_cls=False, use_gpu=False, show_log=False)
except Exception as e:
    logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
    ocr = None

# Text extraction
def extract_text_from_file(filepath):
    """
    Extract text from various file types (PDF, images, TXT, DOC/DOCX).
    Returns extracted text as a string or None if extraction fails.
    """
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

# Initialize default admin
def ensure_default_admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM admins")
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute(
            "INSERT INTO admins (username, password) VALUES (%s, %s)",
            ('admin', 'admin123')
        )
        conn.commit()
        logger.info("Default admin created: username='admin', password='admin123'")
    cursor.close()
    conn.close()

# Initialize default subjects
def ensure_default_subjects():
    default_subjects = {
        '1': ['English', 'Mathematics', 'Environmental Studies'],
        '2': ['English', 'Mathematics', 'Environmental Studies'],
        '3': ['English', 'Mathematics', 'Science', 'Social Studies'],
        '4': ['English', 'Mathematics', 'Science', 'Social Studies'],
        '5': ['English', 'Mathematics', 'Science', 'Social Studies', 'Hindi'],
        '6': ['English', 'Mathematics', 'Science', 'Social Studies', 'Hindi'],
        '7': ['English', 'Mathematics', 'Science', 'Social Studies', 'Hindi'],
        '8': ['English', 'Mathematics', 'Science', 'Social Studies', 'Hindi'],
        '9': ['English', 'Mathematics', 'Physics', 'Chemistry', 'Biology', 'History', 'Geography', 'Civics'],
        '10': ['English', 'Mathematics', 'Physics', 'Chemistry', 'Biology', 'History', 'Geography', 'Civics'],
        '11': ['English', 'Mathematics', 'Physics', 'Chemistry', 'Biology', 'Computer Science', 'Economics', 'Accountancy', 'Business Studies'],
        '12': ['English', 'Mathematics', 'Physics', 'Chemistry', 'Biology', 'Computer Science', 'Economics', 'Accountancy', 'Business Studies']
    }
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM subjects")
    count = cursor.fetchone()[0]
    if count == 0:
        for class_level, subjects in default_subjects.items():
            for subject in subjects:
                cursor.execute(
                    "INSERT INTO subjects (class_level, name) VALUES (%s, %s)",
                    (class_level, subject)
                )
        conn.commit()
        logger.info("Default subjects inserted for classes 1-12")
    cursor.close()
    conn.close()

# Initialize default exam types
def ensure_default_exam_types():
    default_exam_types = ['unit test', 'sliptest', 'premidterm', 'postmidterm', '1st terminal', '2nd terminal']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM exam_types")
    count = cursor.fetchone()[0]
    if count == 0:
        for exam_type in default_exam_types:
            cursor.execute(
                "INSERT INTO exam_types (name) VALUES (%s)",
                (exam_type,)
            )
        conn.commit()
        logger.info("Default exam types inserted")
    cursor.close()
    conn.close()

# Initialize default resource types
def ensure_default_resource_types():
    default_resource_types = ['Textbook', 'Notes', 'Question Paper', 'Syllabus']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM resource_types")
    count = cursor.fetchone()[0]
    if count == 0:
        for resource_type in default_resource_types:
            cursor.execute(
                "INSERT INTO resource_types (name) VALUES (%s)",
                (resource_type,)
            )
        conn.commit()
        logger.info("Default resource types inserted")
    cursor.close()
    conn.close()

# Initialize content table
def ensure_content_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES LIKE 'content'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE content (
                id INT AUTO_INCREMENT PRIMARY KEY,
                class VARCHAR(10) NOT NULL,
                subject VARCHAR(100) NOT NULL,
                book_name VARCHAR(255) NOT NULL,
                chapter VARCHAR(255),
                resource_type VARCHAR(100) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                filepath VARCHAR(255) NOT NULL,
                INDEX idx_class_subject (class, subject)
            )
        """)
        conn.commit()
        logger.info("Created content table in education_db")
    cursor.close()
    conn.close()

# Initialize staff table
def ensure_staff_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES LIKE 'staff'")
    if not cursor.fetchone():
        cursor.execute("""
            CREATE TABLE staff (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                role ENUM('Teacher', 'Admin', 'Support') NOT NULL,
                email VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                created_at DATETIME NOT NULL,
                updated_at DATETIME,
                INDEX idx_role (role)
            )
        """)
        conn.commit()
        logger.info("Created staff table in education_db")
    cursor.close()
    conn.close()

# Initialize default staff
def ensure_default_staff():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM staff")
    count = cursor.fetchone()[0]
    if count == 0:
        default_staff = [
            ('John Doe', 'Teacher', 'john.doe@example.com', '1234567890', datetime.utcnow()),
            ('Jane Smith', 'Admin', 'jane.smith@example.com', '0987654321', datetime.utcnow()),
            ('Bob Johnson', 'Support', 'bob.johnson@example.com', '5555555555', datetime.utcnow())
        ]
        cursor.executemany(
            "INSERT INTO staff (name, role, email, phone, created_at) VALUES (%s, %s, %s, %s, %s)",
            default_staff
        )
        conn.commit()
        logger.info("Inserted default staff: 3 records")
    cursor.close()
    conn.close()

# Call initialization functions
ensure_default_admin()
ensure_default_subjects()
ensure_default_exam_types()
ensure_default_resource_types()
ensure_content_table()
ensure_staff_table()
ensure_default_staff()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE username = %s AND password = %s", (username, password))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        if admin:
            session['admin'] = username
            logger.info(f"Admin logged in: {username}")
            return redirect(url_for('admin_dashboard'))
        logger.warning(f"Failed login attempt: username={username}")
        return render_template('admin_login.html', error='Invalid credentials')
    return render_template('admin_login.html')

@app.route('/logout')
def logout():
    admin = session.pop('admin', None)
    logger.info(f"Admin logged out: {admin}")
    return redirect(url_for('index'))

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        logger.warning("Unauthorized access to admin_dashboard")
        return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html')

@app.route('/upload_content', methods=['GET'])
def upload_content_get():
    if 'admin' not in session:
        logger.warning("Unauthorized access to upload_content")
        return redirect(url_for('admin_login'))
    return render_template('upload_content.html')

@app.route('/upload_content', methods=['POST'])
def upload_content_post():
    if 'admin' not in session:
        logger.warning("Unauthorized access to upload_content POST")
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        form_data = request.form.to_dict()
        logger.info(f"Form data received: {form_data}")
        file = request.files.get('file')
        logger.info(f"File received: {file.filename if file else 'No file'}")
        if not file or file.filename == '':
            logger.warning("No file selected")
            return jsonify({'error': 'No file selected'}), 400
        ext = file.filename.rsplit('.', 1)[-1].lower()
        if ext not in app.config['ALLOWED_EXTENSIONS']:
            logger.warning(f"Unsupported file type: {ext}")
            return jsonify({'error': 'Unsupported file type'}), 400
        # Validate required fields
        required_fields = ['class', 'subject', 'resource_type', 'book_name']
        for field in required_fields:
            if not form_data.get(field):
                logger.warning(f"Missing required field: {field}")
                return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400
        # Verify content table schema
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SHOW COLUMNS FROM content LIKE 'book_name'")
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            logger.error("Schema error: 'book_name' column missing in content table")
            return jsonify({'error': 'Database schema error: book_name column missing'}), 500
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.info(f"File saved: {filepath}")
        # Store in MySQL
        cursor.execute(
            """
            INSERT INTO content (class, subject, book_name, chapter, resource_type, filename, filepath)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                form_data.get('class'),
                form_data.get('subject'),
                form_data.get('book_name'),
                form_data.get('chapter'),
                form_data.get('resource_type'),
                filename,
                filepath
            )
        )
        conn.commit()
        content_id = cursor.lastrowid
        cursor.close()
        conn.close()
        logger.info(f"Content uploaded to MySQL: ID={content_id}, filename={filename}")
        # Extract text and store in MongoDB
        text = extract_text_from_file(filepath)
        metadata = {
            "class": form_data.get('class', ''),
            "subject": form_data.get('subject', ''),
            "book": form_data.get('book_name', 'Unknown'),
            "chapter": form_data.get('chapter', 'Unknown'),
            "chapter_type": form_data.get('resource_type', 'Unknown'),
            "filename": filename
        }
        collection_name = f"class{form_data.get('class')}_{form_data.get('subject').lower().replace(' ', '_')}"
        if store_to_mongo(metadata, text, None, collection_name=collection_name):
            logger.info(f"Successfully stored content in MongoDB: filename={filename}, collection={collection_name}")
        else:
            logger.warning(f"Failed to store content in MongoDB: filename={filename}, collection={collection_name}")
        return jsonify({
            'message': 'Content uploaded successfully!'
        })
    except mysql.connector.errors.ProgrammingError as e:
        logger.exception('Database error during content upload')
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    except Exception as e:
        logger.exception('Error uploading content')
        return jsonify({'error': str(e)}), 500

@app.route('/get_book_names/<class_level>/<subject>')
def get_book_names(class_level, subject):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT book_name FROM content WHERE class = %s AND subject = %s AND book_name IS NOT NULL",
            (class_level, subject)
        )
        book_names = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        logger.info(f"Retrieved book names for class {class_level}, subject {subject}: {book_names}")
        return jsonify(book_names)
    except Exception as e:
        logger.exception(f"Error retrieving book names for class {class_level}, subject {subject}")
        return jsonify({'error': str(e)}), 500

@app.route('/view_uploaded_content', methods=['GET', 'POST'])
def view_uploaded_content():
    if 'admin' not in session:
        logger.warning("Unauthorized access to view_uploaded_content")
        return redirect(url_for('admin_login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT DISTINCT class_level FROM subjects ORDER BY class_level")
        classes = [row['class_level'] for row in cursor.fetchall()]
        contents = []
        selected_class = None
        selected_subject = None
        selected_book_name = None
        if request.method == 'POST':
            selected_class = request.form.get('class')
            selected_subject = request.form.get('subject')
            selected_book_name = request.form.get('book_name')
            if selected_class and selected_subject:
                query = """
                    SELECT id, class, subject, book_name, chapter, resource_type, filename
                    FROM content
                    WHERE class = %s AND subject = %s
                """
                params = [selected_class, selected_subject]
                if selected_book_name:
                    query += " AND book_name = %s"
                    params.append(selected_book_name)
                cursor.execute(query, params)
                contents = cursor.fetchall()
                logger.info(f"Retrieved {len(contents)} content items for class {selected_class}, subject {selected_subject}, book_name {selected_book_name or 'all'}")
        cursor.close()
        conn.close()
        return render_template(
            'view_uploaded_content.html',
            classes=classes,
            contents=contents,
            selected_class=selected_class,
            selected_subject=selected_subject,
            selected_book_name=selected_book_name
        )
    except Exception as e:
        logger.exception('Error retrieving uploaded content')
        return render_template('view_uploaded_content.html', classes=[], error=str(e))

@app.route('/edit_uploaded_content/<content_id>', methods=['GET'])
def edit_uploaded_content_get(content_id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to edit_uploaded_content")
        return redirect(url_for('admin_login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, class, subject, book_name, chapter, resource_type, filename, filepath FROM content WHERE id = %s",
            (content_id,)
        )
        content = cursor.fetchone()
        cursor.execute("SELECT DISTINCT class_level FROM subjects ORDER BY class_level")
        classes = [row['class_level'] for row in cursor.fetchall()]
        cursor.execute("SELECT name FROM resource_types")
        resource_types = [row['name'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        if not content:
            logger.warning(f"Content not found: ID={content_id}")
            return render_template('view_uploaded_content.html', classes=classes, error='Content not found')
        logger.info(f"Retrieved content for editing: ID={content_id}, filename={content['filename']}")
        return render_template('edit_uploaded_content.html', content=content, classes=classes, resource_types=resource_types)
    except Exception as e:
        logger.exception(f"Error retrieving content for editing: ID={content_id}")
        return render_template('view_uploaded_content.html', classes=classes, error=str(e))

@app.route('/edit_uploaded_content/<content_id>', methods=['POST'])
def edit_uploaded_content_post(content_id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to edit_uploaded_content POST")
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        form_data = request.form.to_dict()
        logger.info(f"Form data received for editing content ID={content_id}: {form_data}")
        file = request.files.get('file')
        clear_file = form_data.get('clear_file') == 'on'
        # Validate required fields
        required_fields = ['class', 'subject', 'book_name', 'resource_type']
        for field in required_fields:
            if not form_data.get(field):
                logger.warning(f"Missing required field: {field}")
                return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT filename, filepath, class, subject FROM content WHERE id = %s", (content_id,))
        content = cursor.fetchone()
        if not content:
            cursor.close()
            conn.close()
            logger.warning(f"Content not found: ID={content_id}")
            return jsonify({'error': 'Content not found'}), 404
        old_filepath = content['filepath']
        old_filename = content['filename']
        old_collection_name = f"class{content['class']}_{content['subject'].lower().replace(' ', '_')}"
        new_collection_name = f"class{form_data.get('class')}_{form_data.get('subject').lower().replace(' ', '_')}"
        filename = old_filename
        filepath = old_filepath
        if clear_file:
            filename = None
            filepath = None
            logger.info(f"Clearing existing file for content ID={content_id}")
        elif file and file.filename:
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext not in app.config['ALLOWED_EXTENSIONS']:
                logger.warning(f"Unsupported file type: {ext}")
                return jsonify({'error': 'Unsupported file type'}), 400
            if file.content_length > 10 * 1024 * 1024:
                logger.warning("File size exceeds 10MB limit")
                return jsonify({'error': 'File size exceeds 10MB limit'}), 400
            filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            logger.info(f"New file saved: {filepath}")
        # Update MySQL
        cursor.execute(
            """
            UPDATE content
            SET class = %s, subject = %s, book_name = %s, chapter = %s, resource_type = %s, filename = %s, filepath = %s
            WHERE id = %s
            """,
            (
                form_data.get('class'),
                form_data.get('subject'),
                form_data.get('book_name'),
                form_data.get('chapter'),
                form_data.get('resource_type'),
                filename,
                filepath,
                content_id
            )
        )
        conn.commit()
        cursor.close()
        conn.close()
        # Update MongoDB
        collection = mongo_question_db[new_collection_name]
        mongo_question_db[old_collection_name].delete_one({'filename': old_filename})
        if filename:
            text = extract_text_from_file(filepath) if filepath else None
            metadata = {
                "class": form_data.get('class', ''),
                "subject": form_data.get('subject', ''),
                "book": form_data.get('book_name', 'Unknown'),
                "chapter": form_data.get('chapter', 'Unknown'),
                "chapter_type": form_data.get('resource_type', 'Unknown'),
                "filename": filename
            }
            if store_to_mongo(metadata, text, None, collection_name=new_collection_name):
                logger.info(f"Successfully updated content in MongoDB: filename={filename}, collection={new_collection_name}")
            else:
                logger.warning(f"Failed to update content in MongoDB: filename={filename}, collection={new_collection_name}")
        # Delete old file if replaced or cleared
        if old_filepath and (clear_file or (file and file.filename)) and os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
                logger.info(f"Deleted old file: {old_filepath}")
            except Exception as e:
                logger.warning(f"Failed to delete old file {old_filepath}: {str(e)}")
        logger.info(f"Content updated: ID={content_id}, filename={filename}")
        return jsonify({'message': 'Content updated successfully'})
    except Exception as e:
        logger.exception(f"Error editing content: ID={content_id}")
        return jsonify({'error': str(e)}), 500

@app.route('/delete_uploaded_content/<content_id>', methods=['POST'])
def delete_uploaded_content(content_id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to delete_uploaded_content")
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT filename, filepath, class, subject FROM content WHERE id = %s", (content_id,))
        content = cursor.fetchone()
        if not content:
            cursor.close()
            conn.close()
            logger.warning(f"Content not found: ID={content_id}")
            return jsonify({'error': 'Content not found'}), 404
        # Delete from MySQL
        cursor.execute("DELETE FROM content WHERE id = %s", (content_id,))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Deleted content from MySQL: ID={content_id}, filename={content['filename']}")
        # Delete from MongoDB
        collection_name = f"class{content['class']}_{content['subject'].lower().replace(' ', '_')}"
        try:
            result = mongo_question_db[collection_name].delete_one({'filename': content['filename']})
            if result.deleted_count > 0:
                logger.info(f"Deleted content from MongoDB: filename={content['filename']}, collection={collection_name}")
            else:
                logger.warning(f"No MongoDB document found for filename={content['filename']} in collection={collection_name}")
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed during deletion: {e}")
            return jsonify({'error': f'MongoDB connection failed: {str(e)}'}), 500
        except Exception as e:
            logger.error(f"Error deleting from MongoDB: filename={content['filename']}, collection={collection_name}, error={str(e)}")
        # Delete file from filesystem
        if content['filepath'] and os.path.exists(content['filepath']):
            try:
                os.remove(content['filepath'])
                logger.info(f"Deleted file from filesystem: {content['filepath']}")
            except OSError as e:
                logger.error(f"Failed to delete file {content['filepath']}: {str(e)}")
        logger.info(f"Content deletion completed: ID={content_id}, filename={content['filename']}")
        return jsonify({'message': 'Content deleted successfully'})
    except Exception as e:
        logger.exception(f"Error deleting content: ID={content_id}")
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': str(e)}), 500

@app.route('/get_subjects/<class_level>')
def get_subjects(class_level):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM subjects WHERE class_level = %s", (class_level,))
        subjects = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        logger.info(f"Retrieved subjects for class {class_level}: {subjects}")
        return jsonify(subjects)
    except Exception as e:
        logger.exception(f"Error retrieving subjects for class {class_level}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_subjects_with_id/<class_level>')
def get_subjects_with_id(class_level):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name FROM subjects WHERE class_level = %s", (class_level,))
        subjects = cursor.fetchall()
        cursor.close()
        conn.close()
        logger.info(f"Retrieved subjects with IDs for class {class_level}: {len(subjects)} subjects")
        return jsonify(subjects)
    except Exception as e:
        logger.exception(f"Error retrieving subjects with IDs for class {class_level}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_resource_types')
def get_resource_types():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM resource_types")
        types = [row['name'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        logger.info(f"Retrieved resource types: {types}")
        return jsonify(types)
    except Exception as e:
        logger.exception('Error retrieving resource types')
        return jsonify({'error': str(e)}), 500

@app.route('/get_exam_patterns/<class_level>')
def get_exam_patterns(class_level):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, class_level FROM exam_patterns WHERE class_level = %s", (class_level,))
        patterns = cursor.fetchall()
        cursor.close()
        conn.close()
        logger.info(f"Retrieved exam patterns for class {class_level}: {len(patterns)} patterns")
        return jsonify(patterns)
    except Exception as e:
        logger.exception(f"Error retrieving exam patterns for class {class_level}")
        return jsonify({'error': str(e)}), 500

@app.route('/create_exam_pattern', methods=['GET', 'POST'])
def create_exam_pattern():
    if 'admin' not in session:
        logger.warning("Unauthorized access to create_exam_pattern")
        return jsonify({'error': 'Unauthorized'}), 401
    if request.method == 'POST':
        try:
            class_level = request.form.get('class')
            exam_type = request.form.get('exam_type')
            custom_exam_type = request.form.get('custom_exam_type')
            marking_scheme = request.form.get('marking_scheme')
            chapters = request.form.getlist('chapters')
            custom_chapter = request.form.get('custom_chapter')
            logger.info(f"Attempting to create exam pattern: class_level={class_level}, exam_type={exam_type}, chapters={chapters}")
            if not class_level or not exam_type or not marking_scheme:
                logger.warning("Missing required fields: class_level, exam_type, or marking_scheme")
                return jsonify({'error': 'Class, exam type, and marking_scheme are required'}), 400
            if not chapters and not custom_chapter:
                logger.warning("No chapters selected")
                return jsonify({'error': 'At least one chapter is required'}), 400
            if exam_type == 'other':
                exam_type = custom_exam_type
                if not exam_type:
                    logger.warning("Custom exam type not provided")
                    return jsonify({'error': 'Custom exam type is required'}), 400
            if custom_chapter:
                chapters.append(custom_chapter)
            chapters_str = ','.join(chapters)
            filename = None
            filepath = None
            if 'file' in request.files:
                file = request.files['file']
                if file and file.filename:
                    ext = file.filename.rsplit('.', 1)[-1].lower()
                    if ext not in app.config['ALLOWED_EXTENSIONS']:
                        logger.warning(f"Unsupported file type: {ext}")
                        return jsonify({'error': 'Unsupported file type. Allowed: pdf, doc, docx, txt'}), 400
                    if file.content_length > 10 * 1024 * 1024:
                        logger.warning("File size exceeds 10MB limit")
                        return jsonify({'error': 'File size exceeds 10MB limit'}), 400
                    filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    logger.info(f"File saved: {filepath}")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO exam_patterns (name, description, class_level, chapters, filename, filepath)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (exam_type, marking_scheme, class_level, chapters_str, filename, filepath)
            )
            conn.commit()
            pattern_id = cursor.lastrowid
            cursor.close()
            conn.close()
            logger.info(f"Exam pattern created: ID={pattern_id}, class_level={class_level}, exam_type={exam_type}")
            return jsonify({'message': 'Exam pattern created successfully', 'pattern_id': pattern_id})
        except Exception as e:
            logger.exception('Error creating exam pattern')
            return jsonify({'error': str(e)}), 500
    return render_template('create_exam_pattern.html')

@app.route('/edit_exam_pattern', methods=['GET'])
def edit_exam_pattern_get():
    if 'admin' not in session:
        logger.warning("Unauthorized access to edit_exam_pattern")
        return redirect(url_for('admin_login'))
    return render_template('edit_exam_pattern.html')

@app.route('/edit_exam_pattern/<pattern_id>', methods=['GET'])
def edit_exam_pattern_details(pattern_id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to edit_exam_pattern_details")
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, name, description, class_level, chapters, filename
            FROM exam_patterns WHERE id = %s
            """,
            (pattern_id,)
        )
        pattern = cursor.fetchone()
        cursor.close()
        conn.close()
        if not pattern:
            logger.warning(f"Exam pattern not found: ID={pattern_id}")
            return jsonify({'error': 'Exam pattern not found'}), 404
        pattern['chapters'] = pattern['chapters'].split(',') if pattern['chapters'] else []
        logger.info(f"Retrieved exam pattern details: ID={pattern_id}, name={pattern['name']}")
        return jsonify(pattern)
    except Exception as e:
        logger.exception(f"Error retrieving exam pattern details: ID={pattern_id}")
        return jsonify({'error': str(e)}), 500

@app.route('/edit_exam_pattern/<pattern_id>', methods=['POST'])
def edit_exam_pattern_post(pattern_id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to edit_exam_pattern POST")
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        class_level = request.form.get('class')
        exam_type = request.form.get('exam_type')
        custom_exam_type = request.form.get('custom_exam_type')
        marking_scheme = request.form.get('marking_scheme')
        chapters = request.form.getlist('chapters')
        custom_chapter = request.form.get('custom_chapter')
        clear_file = request.form.get('clear_file') == 'on'
        logger.info(f"Attempting to edit exam pattern: ID={pattern_id}, class_level={class_level}, exam_type={exam_type}, chapters={chapters}, clear_file={clear_file}")
        if not class_level or not exam_type or not marking_scheme:
            logger.warning("Missing required fields: class_level, exam_type, or marking_scheme")
            return jsonify({'error': 'Class, exam type, and marking_scheme are required'}), 400
        if not chapters and not custom_chapter:
            logger.warning("No chapters selected")
            return jsonify({'error': 'At least one chapter is required'}), 400
        if exam_type == 'other':
            exam_type = custom_exam_type
            if not exam_type:
                logger.warning("Custom exam type not provided")
                return jsonify({'error': 'Custom exam type is required'}), 400
        if custom_chapter:
            chapters.append(custom_chapter)
        chapters_str = ','.join(chapters)
        filename = None
        filepath = None
        old_filepath = None
        if clear_file:
            logger.info(f"Clearing existing file for pattern ID={pattern_id}")
        elif 'file' in request.files:
            file = request.files['file']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext not in app.config['ALLOWED_EXTENSIONS']:
                    logger.warning(f"Unsupported file type: {ext}")
                    return jsonify({'error': 'Unsupported file type. Allowed: pdf, doc, docx, txt'}), 400
                if file.content_length > 10 * 1024 * 1024:
                    logger.warning("File size exceeds 10MB limit")
                    return jsonify({'error': 'File size exceeds 10MB limit'}), 400
                filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                logger.info(f"New file saved: {filepath}")
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, filepath FROM exam_patterns WHERE id = %s", (pattern_id,))
        pattern = cursor.fetchone()
        if not pattern:
            cursor.close()
            conn.close()
            logger.warning(f"Exam pattern not found: ID={pattern_id}")
            return jsonify({'error': 'Exam pattern not found'}), 404
        old_filepath = pattern['filepath']
        cursor.execute(
            "SELECT COUNT(*) FROM exam_patterns WHERE name = %s AND class_level = %s AND id != %s",
            (exam_type, class_level, pattern_id)
        )
        if cursor.fetchone()['COUNT(*)'] > 0:
            cursor.close()
            conn.close()
            logger.warning(f"Duplicate exam pattern detected: {exam_type} for class {class_level}")
            return jsonify({'error': 'Exam pattern already exists for this class'}), 400
        cursor.execute(
            """
            UPDATE exam_patterns
            SET name = %s, description = %s, class_level = %s, chapters = %s, filename = %s, filepath = %s
            WHERE id = %s
            """,
            (exam_type, marking_scheme, class_level, chapters_str, filename if not clear_file else None, filepath if not clear_file else None, pattern_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        if old_filepath and (clear_file or filename) and os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
                logger.info(f"Deleted old file: {old_filepath}")
            except Exception as e:
                logger.warning(f"Failed to delete old file {old_filepath}: {str(e)}")
        logger.info(f"Exam pattern updated: ID={pattern_id}, class_level={class_level}, exam_type={exam_type}")
        return jsonify({'message': 'Exam pattern updated successfully', 'pattern_id': pattern_id})
    except Exception as e:
        logger.exception('Error editing exam pattern')
        return jsonify({'error': str(e)}), 500

@app.route('/delete_exam_pattern/<pattern_id>', methods=['POST'])
def delete_exam_pattern(pattern_id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to delete_exam_pattern")
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, filepath FROM exam_patterns WHERE id = %s", (pattern_id,))
        pattern = cursor.fetchone()
        if not pattern:
            cursor.close()
            conn.close()
            logger.warning(f"Exam pattern not found: ID={pattern_id}")
            return jsonify({'error': 'Exam pattern not found'}), 404
        cursor.execute("DELETE FROM exam_patterns WHERE id = %s", (pattern_id,))
        conn.commit()
        cursor.close()
        conn.close()
        if pattern['filepath'] and os.path.exists(pattern['filepath']):
            try:
                os.remove(pattern['filepath'])
                logger.info(f"Deleted file: {pattern['filepath']}")
            except Exception as e:
                logger.warning(f"Failed to delete file {pattern['filepath']}: {str(e)}")
        logger.info(f"Exam pattern deleted: ID={pattern_id}")
        return jsonify({'message': 'Exam pattern deleted successfully'})
    except Exception as e:
        logger.exception(f"Error deleting exam pattern: ID={pattern_id}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate_question_paper', methods=['GET', 'POST'])
def generate_question_paper():
    if 'admin' not in session:
        logger.warning("Unauthorized access to generate_question_paper")
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        try:
            class_level = request.form.get('class_level')
            subject = request.form.get('subject')
            exam_pattern_id = request.form.get('exam_pattern_id')
            difficulty = request.form.get('difficulty', 'easy')
            file = request.files.get('file')
            logger.info(f"Attempting to generate question paper: class_level={class_level}, subject={subject}, exam_pattern_id={exam_pattern_id}, difficulty={difficulty}")
            result = generate_question_paper(
                class_level=class_level,
                subject=subject,
                exam_pattern_id=exam_pattern_id,
                difficulty=difficulty,
                file=file,
                upload_folder=app.config['UPLOAD_FOLDER'],
                output_folder=app.config['OUTPUT_FOLDER']
            )
            if result.get('success'):
                output_filepath = result.get('filepath')
                output_filename = os.path.basename(output_filepath)
                text = extract_text_from_file(output_filepath)
                metadata = {
                    "class": class_level,
                    "subject": subject,
                    "book": "Question Paper",
                    "chapter_type": "Question Paper",
                    "filename": output_filename
                }
                collection_name = f"class{class_level}_{subject.lower().replace(' ', '_')}"
                if store_to_mongo(metadata, text, None, collection_name=collection_name):
                    logger.info(f"Successfully stored question paper in MongoDB: filename={output_filename}, collection={collection_name}")
                else:
                    logger.warning(f"Failed to store question paper in MongoDB: filename={output_filename}, collection={collection_name}")
                return jsonify(result)
        except Exception as e:
            logger.exception('Error generating question paper')
            return jsonify({'error': str(e)}), 500
    return render_template('generate_question_paper.html')

@app.route('/static/outputs/<path:filename>')
def download_file(filename):
    try:
        logger.info(f"Serving file: {filename}")
        return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        logger.exception(f"Error serving file: {filename}")
        return jsonify({'error': str(e)}), 404

@app.route('/manage_subjects', methods=['GET', 'POST'])
def manage_subjects():
    if 'admin' not in session:
        logger.warning("Unauthorized access to manage_subjects")
        return jsonify({'error': 'Unauthorized'}), 401
    if request.method == 'POST':
        class_level = request.form.get('class_level')
        subject_name = request.form.get('subject_name')
        logger.info(f"Attempting to add subject: class_level={class_level}, subject_name={subject_name}")
        if not class_level or not subject_name:
            logger.warning("Missing class_level or subject_name")
            return jsonify({'error': 'Class and subject name are required'}), 400
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM subjects WHERE class_level = %s AND name = %s",
                (class_level, subject_name)
            )
            if cursor.fetchone()[0] > 0:
                cursor.close()
                conn.close()
                logger.warning(f"Duplicate subject detected: {subject_name} for class {class_level}")
                return jsonify({'error': 'Subject already exists for this class'}), 400
            cursor.execute(
                "INSERT INTO subjects (class_level, name) VALUES (%s, %s)",
                (class_level, subject_name)
            )
            conn.commit()
            subject_id = cursor.lastrowid
            cursor.close()
            conn.close()
            logger.info(f"Subject added successfully: ID={subject_id}, class_level={class_level}, subject_name={subject_name}")
            return jsonify({'message': 'Subject added successfully', 'subject_id': subject_id})
        except Exception as e:
            logger.exception('Error adding subject')
            return jsonify({'error': str(e)}), 500
    return render_template('manage_subjects.html')

@app.route('/edit_subject/<subject_id>', methods=['POST'])
def edit_subject(subject_id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to edit_subject")
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        data = request.get_json()
        class_level = data.get('class_level')
        subject_name = data.get('subject_name')
        logger.info(f"Attempting to edit subject: ID={subject_id}, class_level={class_level}, subject_name={subject_name}")
        if not class_level or not subject_name:
            logger.warning("Missing class_level or subject_name")
            return jsonify({'error': 'Class and subject name are required'}), 400
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM subjects WHERE class_level = %s AND name = %s AND id != %s",
            (class_level, subject_name, subject_id)
        )
        if cursor.fetchone()[0] > 0:
            cursor.close()
            conn.close()
            logger.warning(f"Duplicate subject detected: {subject_name} for class {class_level}")
            return jsonify({'error': 'Subject already exists for this class'}), 400
        cursor.execute(
            "UPDATE subjects SET class_level = %s, name = %s WHERE id = %s",
            (class_level, subject_name, subject_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Subject updated successfully: ID={subject_id}, class_level={class_level}, subject_name={subject_name}")
        return jsonify({'message': 'Subject updated successfully'})
    except Exception as e:
        logger.exception('Error editing subject')
        return jsonify({'error': str(e)}), 500

@app.route('/delete_subject/<subject_id>', methods=['POST'])
def delete_subject(subject_id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to delete_subject")
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM subjects WHERE id = %s", (subject_id,))
        if cursor.fetchone()[0] == 0:
            cursor.close()
            conn.close()
            logger.warning(f"Subject not found: ID={subject_id}")
            return jsonify({'error': 'Subject not found'}), 404
        cursor.execute(
            "SELECT COUNT(*) FROM content WHERE subject = (SELECT name FROM subjects WHERE id = %s)",
            (subject_id,)
        )
        if cursor.fetchone()[0] > 0:
            cursor.close()
            conn.close()
            logger.warning(f"Cannot delete subject ID={subject_id}; used in content")
            return jsonify({'error': 'Cannot delete subject; it is used in content'}), 400
        cursor.execute("DELETE FROM subjects WHERE id = %s", (subject_id,))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Subject deleted successfully: ID={subject_id}")
        return jsonify({'message': 'Subject deleted successfully'})
    except Exception as e:
        logger.exception('Error deleting subject')
        return jsonify({'error': str(e)}), 500

@app.route('/get_chapters/<class_level>')
def get_chapters(class_level):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT chapter FROM content WHERE class = %s", (class_level,))
        content_chapters = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT name FROM chapters WHERE class = %s", (class_level,))
        custom_chapters = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        chapters = list(set(content_chapters + custom_chapters))
        logger.info(f"Retrieved chapters for class {class_level}: {chapters}")
        return jsonify(chapters)
    except Exception as e:
        logger.exception(f"Error retrieving chapters for class {class_level}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_exam_types')
def get_exam_types():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM exam_types")
        types = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        logger.info(f"Retrieved exam types: {types}")
        return jsonify(types)
    except Exception as e:
        logger.exception('Error retrieving exam types')
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        logger.info("Health check: OK")
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.exception('Health check failed')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/analytics')
def analytics():
    if 'admin' not in session:
        logger.warning("Unauthorized access to analytics")
        return redirect(url_for('admin_login'))
    return render_template('analytics.html')

@app.route('/get_analytics', methods=['GET'])
def get_analytics():
    if 'admin' not in session:
        logger.warning("Unauthorized access to get_analytics")
        return jsonify({'error': 'Unauthorized'}), 401
    class_level = request.args.get('class_level', '')
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(DISTINCT class_level) AS total_classes FROM subjects")
        total_classes = cursor.fetchone()['total_classes']
        cursor.execute("SELECT COUNT(*) AS total_subjects FROM subjects")
        total_subjects = cursor.fetchone()['total_subjects']
        cursor.execute("SELECT COUNT(*) AS total_resources FROM content")
        total_resources = cursor.fetchone()['total_resources']
        cursor.execute("SELECT COUNT(*) AS total_books FROM content WHERE resource_type = 'Textbook'")
        total_books = cursor.fetchone()['total_books']
        cursor.execute("SELECT COUNT(*) AS total_notes FROM content WHERE resource_type = 'Notes'")
        total_notes = cursor.fetchone()['total_notes']
        cursor.execute("SELECT COUNT(*) AS total_patterns FROM exam_patterns")
        total_patterns = cursor.fetchone()['total_patterns']
        cursor.execute("SELECT COUNT(*) AS total_staff FROM staff")
        total_staff = cursor.fetchone()['total_staff']
        class_analytics = None
        if class_level:
            cursor.execute("SELECT COUNT(*) AS subjects FROM subjects WHERE class_level = %s", (class_level,))
            subjects = cursor.fetchone()['subjects']
            cursor.execute("SELECT COUNT(*) AS resources FROM content WHERE class = %s", (class_level,))
            resources = cursor.fetchone()['resources']
            cursor.execute("SELECT COUNT(*) AS books FROM content WHERE class = %s AND resource_type = 'Textbook'", (class_level,))
            books = cursor.fetchone()['books']
            cursor.execute("SELECT COUNT(*) AS notes FROM content WHERE class = %s AND resource_type = 'Notes'", (class_level,))
            notes = cursor.fetchone()['notes']
            cursor.execute("SELECT COUNT(*) AS patterns FROM exam_patterns WHERE class_level = %s", (class_level,))
            patterns = cursor.fetchone()['patterns']
            class_analytics = {
                'class_level': class_level,
                'subjects': subjects,
                'resources': resources,
                'books': books,
                'notes': notes,
                'patterns': patterns
            }
        cursor.execute("SELECT DISTINCT class_level FROM subjects ORDER BY class_level")
        classes = [row['class_level'] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        analytics = {
            'total_classes': total_classes,
            'total_subjects': total_subjects,
            'total_resources': total_resources,
            'total_books': total_books,
            'total_notes': total_notes,
            'total_patterns': total_patterns,
            'total_staff': total_staff,
            'classes': classes,
            'class_analytics': class_analytics
        }
        logger.info(f"Retrieved analytics: total_classes={total_classes}, total_staff={total_staff}, class_level={class_level or 'all'}")
        return jsonify(analytics)
    except Exception as e:
        logger.error(f"Error retrieving analytics for class_level={class_level or 'all'}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/view_staff', methods=['GET'])
def view_staff():
    if 'admin' not in session:
        logger.warning("Unauthorized access to view_staff")
        return redirect(url_for('admin_login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        role_filter = request.args.get('role', 'all')
        if role_filter == 'all':
            cursor.execute("SELECT id, name, role, email, phone, created_at, updated_at FROM staff ORDER BY name")
        else:
            cursor.execute(
                "SELECT id, name, role, email, phone, created_at, updated_at FROM staff WHERE role = %s ORDER BY name",
                (role_filter,)
            )
        staff = cursor.fetchall()
        cursor.close()
        conn.close()
        logger.info(f"Retrieved {len(staff)} staff members with role_filter={role_filter}")
        return render_template('view_staff.html', staff=staff, role_filter=role_filter)
    except Exception as e:
        logger.error(f"Error retrieving staff: {str(e)}")
        return render_template('view_staff.html', staff=[], role_filter=role_filter, error=str(e))

@app.route('/add_staff', methods=['POST'])
def add_staff():
    if 'admin' not in session:
        logger.warning("Unauthorized access to add_staff")
        return redirect(url_for('admin_login'))
    try:
        name = request.form['name']
        role = request.form['role']
        email = request.form['email']
        phone = request.form.get('phone', '')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO staff (name, role, email, phone, created_at) VALUES (%s, %s, %s, %s, %s)",
            (name, role, email, phone, datetime.utcnow())
        )
        conn.commit()
        staff_id = cursor.lastrowid
        cursor.close()
        conn.close()
        logger.info(f"Staff added: id={staff_id}, name={name}")
        return redirect(url_for('view_staff'))
    except Exception as e:
        logger.error(f"Error adding staff: {str(e)}")
        return redirect(url_for('view_staff'))

@app.route('/edit_staff/<id>', methods=['GET', 'POST'])
def edit_staff(id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to edit_staff")
        return redirect(url_for('admin_login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, role, email, phone, created_at, updated_at FROM staff WHERE id = %s", (id,))
        staff = cursor.fetchone()
        if not staff:
            cursor.close()
            conn.close()
            logger.warning(f"Staff not found: id={id}")
            return redirect(url_for('view_staff'))
        if request.method == 'POST':
            name = request.form['name']
            role = request.form['role']
            email = request.form['email']
            phone = request.form.get('phone', '')
            cursor.execute(
                """
                UPDATE staff
                SET name = %s, role = %s, email = %s, phone = %s, updated_at = %s
                WHERE id = %s
                """,
                (name, role, email, phone, datetime.utcnow(), id)
            )
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"Staff updated: id={id}, name={name}")
            return redirect(url_for('view_staff'))
        cursor.close()
        conn.close()
        return render_template('edit_staff.html', staff=staff)
    except Exception as e:
        logger.error(f"Error editing staff: {str(e)}")
        return redirect(url_for('view_staff'))

@app.route('/delete_staff/<id>', methods=['GET'])
def delete_staff(id):
    if 'admin' not in session:
        logger.warning("Unauthorized access to delete_staff")
        return redirect(url_for('admin_login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM staff WHERE id = %s", (id,))
        staff = cursor.fetchone()
        if not staff:
            cursor.close()
            conn.close()
            logger.warning(f"Staff not found: id={id}")
            return redirect(url_for('view_staff'))
        cursor.execute("DELETE FROM staff WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Staff deleted: id={id}, name={staff[0]}")
        return redirect(url_for('view_staff'))
    except Exception as e:
        logger.error(f"Error deleting staff: {str(e)}")
        return redirect(url_for('view_staff'))

if __name__ == '__main__':
    app.run(debug=True, host="localhost", port=5000)