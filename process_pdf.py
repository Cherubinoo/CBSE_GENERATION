import os
import json
import requests
from bson.objectid import ObjectId
from datetime import datetime
from convert import extract_text_from_pdf

def get_embedding_from_gpu(text):
    try:
        response = requests.post(
            "http://localhost:5001/generate_embedding",  # Replace if GPU server is remote
            json={"text": text},
            timeout=60
        )
        response_data = response.json()
        if "error" in response_data:
            raise Exception(response_data["error"])
        return response_data.get('embedding')
    except Exception as e:
        return {"error": str(e)}

def process_uploaded_pdf(filepath, form_data, db):
    try:
        # Step 1: Extract text from PDF
        text = extract_text_from_pdf(filepath)
        if not text:
            return {'status': 'error', 'message': 'Text extraction failed'}

        # Step 2: Send text to GPU server for embeddings
        embeddings = get_embedding_from_gpu(text)
        if isinstance(embeddings, dict) and embeddings.get("error"):
            return {'status': 'error', 'message': f"Embedding failed: {embeddings['error']}"}

        # Step 3: Prepare metadata
        metadata = {
            'class': form_data.get('class'),
            'subject': form_data.get('subject') or form_data.get('custom_subject'),
            'resource_type': form_data.get('resource_type') or form_data.get('custom_resource_type'),
            'chapter': form_data.get('chapter'),
            'original_filename': os.path.basename(filepath),
            'text': text,
            'embeddings': embeddings,
            'upload_date': datetime.utcnow()
        }

        # Step 4: Store in MongoDB
        content_collection = db['content']
        result = content_collection.insert_one(metadata)
        content_id = str(result.inserted_id)

        return {
            'status': 'success',
            'message': 'PDF processed and stored successfully!',
            'content_id': content_id
        }

    except Exception as e:
        return {'status': 'error', 'message': str(e)}
 