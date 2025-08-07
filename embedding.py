from flask import Flask, request, jsonify
import logging
from sentence_transformers import SentenceTransformer
import socket
import time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('EMBEDDING')

app = Flask(__name__)

# Cache model in a local directory
MODEL_CACHE_DIR = './model_cache'
try:
    logger.info("Loading SentenceTransformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu', cache_folder=MODEL_CACHE_DIR)
    logger.info("SentenceTransformer model loaded successfully")
except Exception as e:
    logger.error(f"Failed to load SentenceTransformer model: {str(e)}")
    raise

def is_port_in_use(port):
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except socket.error:
            return True

def free_port(port):
    """Attempt to free a port by closing any sockets."""
    try:
        for conn in socket.getaddrinfo('0.0.0.0', port, socket.AF_INET, socket.SOCK_STREAM):
            sock = socket.socket(conn[0], conn[1])
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', port))
                sock.close()
            except socket.error:
                continue
    except Exception as e:
        logger.warning(f"Error freeing port {port}: {str(e)}")

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/generate_embedding', methods=['POST'])
def generate_embedding():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            logger.warning("No text provided in request")
            return jsonify({'error': 'Text is required'}), 400
        
        text = data['text']
        if not text.strip():
            logger.warning("Empty text provided for embedding")
            return jsonify({'error': 'Text cannot be empty'}), 400

        logger.info(f"Generating embedding for text (length: {len(text)})")
        embedding = model.encode(text, convert_to_tensor=False).tolist()
        logger.info(f"Embedding generated successfully (length: {len(embedding)})")
        return jsonify({'embedding': embedding})
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = 5001
    max_retries = 3
    retry_delay = 5
    for attempt in range(max_retries):
        if not is_port_in_use(port):
            try:
                logger.info(f"Starting Flask server on port {port} (attempt {attempt + 1}/{max_retries})")
                app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)
                break
            except Exception as e:
                logger.error(f"Failed to start server on attempt {attempt + 1}: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
        else:
            logger.warning(f"Port {port} in use, attempting to free it...")
            free_port(port)
            time.sleep(retry_delay)
    else:
        logger.error(f"Failed to start server after {max_retries} attempts")
        raise Exception("Unable to start embedding server")