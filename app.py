from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import uuid
from werkzeug.utils import secure_filename
import threading
import time
import shutil
from pathlib import Path
from config import Config
from utils.file_processor import TaxDocumentProcessor

app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Global variables for processing
processing_status = {}
processor = None
processor_initializing = False

def init_processor_background():
    """Initialize the document processor in background"""
    global processor, processor_initializing

    processor_initializing = True
    print("Starting background processor initialization...")

    try:
        if not Config.ANTHROPIC_API_KEY or Config.ANTHROPIC_API_KEY.strip() == '':
            print("Warning: ANTHROPIC_API_KEY not set. Document processing will be limited.")
            processor = None
            processor_initializing = False
            return

        print("Loading Donut model and Claude API...")
        processor = TaxDocumentProcessor(
            donut_model_path=Config.DONUT_MODEL_PATH,
            claude_api_key=Config.ANTHROPIC_API_KEY
        )
        print("Document processor initialized successfully")
        processor_initializing = False

    except Exception as e:
        print(f"Error initializing processor: {e}")
        print("Document processing will be unavailable")
        processor = None
        processor_initializing = False

def init_processor():
    """Start processor initialization in background thread"""
    import threading

    # Start background initialization
    init_thread = threading.Thread(target=init_processor_background, daemon=True)
    init_thread.start()

    return True  # Always allow app to start

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def process_documents_background(session_id, file_paths):
    """Background function to process documents"""
    global processing_status, processor

    if not processor:
        processing_status[session_id]['status'] = 'error'
        processing_status[session_id]['error'] = 'Document processor not initialized'
        return

    try:
        total_files = len(file_paths)
        processing_status[session_id]['total'] = total_files
        processing_status[session_id]['results'] = []

        # Initialize all files with "waiting" status
        for _, original_filename in file_paths:
            processing_status[session_id]['results'].append({
                'original_filename': original_filename,
                'status': 'waiting',
                'client_name': None,
                'document_type': None,
                'tax_year': None,
                'new_filename': None,
                'error': None
            })

        # Get manual client info if available
        manual_client_info = processing_status[session_id].get('manual_client_info')

        for i, (file_path, original_filename) in enumerate(file_paths):
            # Update progress
            processing_status[session_id]['current'] = i + 1
            processing_status[session_id]['current_file'] = original_filename

            # Update status to processing for current file
            processing_status[session_id]['results'][i]['status'] = 'processing'

            # Process the document with manual client info if provided
            result = processor.process_document(file_path, original_filename, manual_client_info)

            # Update the result in the status
            processing_status[session_id]['results'][i] = result

            # Clean up uploaded file
            try:
                os.remove(file_path)
            except:
                pass

        # Generate statistics
        stats = processor.get_processing_stats(processing_status[session_id]['results'])
        processing_status[session_id]['stats'] = stats
        processing_status[session_id]['status'] = 'completed'

    except Exception as e:
        processing_status[session_id]['status'] = 'error'
        processing_status[session_id]['error'] = str(e)

@app.route('/')
def index():
    """Main page with upload interface"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file upload and start processing"""
    global processing_status, processor, processor_initializing

    if processor_initializing:
        return jsonify({'error': 'Document processor is still initializing. Please wait a moment and try again.'}), 503

    if not processor:
        return jsonify({'error': 'Document processor not initialized. Please set your Claude API key in Settings.'}), 500

    # Check if files were uploaded
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected'}), 400

    # Get processing mode and client info
    processing_mode = request.form.get('processing_mode', 'auto')
    manual_client_info = None

    if processing_mode == 'manual':
        first_name = request.form.get('client_first_name', '').strip()
        last_name = request.form.get('client_last_name', '').strip()

        if not first_name or not last_name:
            return jsonify({'error': 'First name and last name required for manual mode'}), 400

        manual_client_info = {
            'first_name': first_name,
            'last_name': last_name
        }

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Save uploaded files
    file_paths = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(Config.UPLOAD_FOLDER, f"{session_id}_{filename}")
            file.save(file_path)
            file_paths.append((file_path, filename))

    if not file_paths:
        return jsonify({'error': 'No valid files uploaded'}), 400

    # Initialize processing status
    processing_status[session_id] = {
        'status': 'processing',
        'total': len(file_paths),
        'current': 0,
        'current_file': '',
        'results': [],
        'stats': {},
        'error': None,
        'processing_mode': processing_mode,
        'manual_client_info': manual_client_info
    }

    # Start background processing
    thread = threading.Thread(
        target=process_documents_background,
        args=(session_id, file_paths)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'session_id': session_id})

@app.route('/status/<session_id>')
def get_status(session_id):
    """Get processing status for a session"""
    global processing_status

    if session_id not in processing_status:
        return jsonify({'error': 'Session not found'}), 404

    return jsonify(processing_status[session_id])

@app.route('/results/<session_id>')
def get_results(session_id):
    """Get processing results for a session"""
    global processing_status

    if session_id not in processing_status:
        return jsonify({'error': 'Session not found'}), 404

    status = processing_status[session_id]
    if status['status'] != 'completed':
        return jsonify({'error': 'Processing not completed'}), 400

    return jsonify({
        'results': status['results'],
        'stats': status['stats']
    })

# File Explorer API endpoints
@app.route('/api/directory')
@app.route('/api/directory/')
@app.route('/api/directory/<path:dir_path>')
def get_directory_contents(dir_path=''):
    """Get contents of a directory"""
    try:
        # Build full path
        if not dir_path or dir_path == 'processed':
            full_path = Config.PROCESSED_FOLDER
            relative_path = 'processed'
        else:
            # Remove 'processed/' prefix if present
            if dir_path.startswith('processed/'):
                dir_path = dir_path[10:]
            full_path = os.path.join(Config.PROCESSED_FOLDER, dir_path)
            relative_path = f"processed/{dir_path}" if dir_path else 'processed'

        # Ensure the directory exists
        if not os.path.exists(full_path):
            os.makedirs(full_path, exist_ok=True)

        # Get directory contents
        dirs = []
        files = []

        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            if os.path.isdir(item_path):
                dirs.append(item)
            else:
                files.append(item)

        return jsonify({
            'success': True,
            'fullPath': full_path,
            'relativePath': relative_path,
            'dirs': sorted(dirs),
            'files': sorted(files)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/rename', methods=['POST'])
def rename_item():
    """Rename a file or folder"""
    try:
        data = request.json
        old_path = data.get('oldPath', '')
        new_name = data.get('newName', '')
        new_path = data.get('newPath', '')

        # Build full paths
        if old_path.startswith('processed/'):
            old_path = old_path[10:]

        old_full_path = os.path.join(Config.PROCESSED_FOLDER, old_path) if old_path else Config.PROCESSED_FOLDER

        if new_path:
            # Moving to a different directory
            if new_path.startswith('processed/'):
                new_path = new_path[10:]
            new_full_path = os.path.join(Config.PROCESSED_FOLDER, new_path) if new_path else Config.PROCESSED_FOLDER
        else:
            # Renaming in the same directory
            old_dir = os.path.dirname(old_full_path)
            new_full_path = os.path.join(old_dir, new_name)

        # Check if source exists
        if not os.path.exists(old_full_path):
            return jsonify({
                'success': False,
                'error': 'Source file or folder not found'
            }), 404

        # Check if destination already exists
        if os.path.exists(new_full_path):
            return jsonify({
                'success': False,
                'error': 'A file or folder with that name already exists'
            }), 400

        # Perform the rename/move
        shutil.move(old_full_path, new_full_path)

        return jsonify({
            'success': True,
            'message': 'Item renamed successfully'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/create-folder', methods=['POST'])
def create_folder():
    """Create a new folder"""
    try:
        data = request.json
        parent_path = data.get('path', 'processed')
        folder_name = data.get('folderName', '')

        if not folder_name:
            return jsonify({
                'success': False,
                'error': 'Folder name is required'
            }), 400

        # Build full path
        if parent_path == 'processed' or not parent_path:
            full_parent_path = Config.PROCESSED_FOLDER
        else:
            if parent_path.startswith('processed/'):
                parent_path = parent_path[10:]
            full_parent_path = os.path.join(Config.PROCESSED_FOLDER, parent_path)

        new_folder_path = os.path.join(full_parent_path, folder_name)

        # Check if folder already exists
        if os.path.exists(new_folder_path):
            return jsonify({
                'success': False,
                'error': 'A folder with that name already exists'
            }), 400

        # Create the folder
        os.makedirs(new_folder_path)

        return jsonify({
            'success': True,
            'message': 'Folder created successfully'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/open-folder', methods=['POST'])
def open_folder():
    """Open folder in system file explorer"""
    try:
        data = request.json
        folder_path = data.get('path', 'processed')

        # Build full path
        if folder_path == 'processed' or not folder_path:
            full_path = Config.PROCESSED_FOLDER
        else:
            if folder_path.startswith('processed/'):
                folder_path = folder_path[10:]
            full_path = os.path.join(Config.PROCESSED_FOLDER, folder_path)

        # Ensure directory exists
        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'error': 'Folder not found'
            }), 404

        # Open folder in system file explorer
        import subprocess
        import platform

        system = platform.system()
        if system == 'Darwin':  # macOS
            subprocess.run(['open', full_path])
        elif system == 'Windows':
            subprocess.run(['explorer', full_path])
        else:  # Linux
            subprocess.run(['xdg-open', full_path])

        return jsonify({
            'success': True,
            'message': 'Folder opened in file explorer'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/download/<path:filename>')
def download_file(filename):
    """Download processed files"""
    return send_from_directory(Config.PROCESSED_FOLDER, filename, as_attachment=True)

@app.route('/preview/<path:filename>')
def preview_file(filename):
    """Serve processed files for preview (not as download)"""
    try:
        print(f"Preview request for: {filename}")

        # Handle URL decoding properly
        import urllib.parse
        decoded_filename = urllib.parse.unquote(filename)

        # Normalize path separators
        normalized_filename = decoded_filename.replace('\\', '/')

        # Construct full path
        full_path = os.path.join(Config.PROCESSED_FOLDER, normalized_filename)
        full_path = os.path.normpath(full_path)

        # Security check - ensure path is within processed folder
        processed_folder_abs = os.path.abspath(Config.PROCESSED_FOLDER)
        full_path_abs = os.path.abspath(full_path)

        if not full_path_abs.startswith(processed_folder_abs):
            print(f"SECURITY ERROR: Path traversal attempt detected for {filename}")
            return jsonify({'error': 'Invalid file path'}), 400

        if not os.path.exists(full_path):
            print(f"File not found: {full_path}")

            # Try different decoding approaches
            alternatives = [
                filename,  # Use original filename as-is
                urllib.parse.unquote_plus(filename),  # Try unquote_plus for + encoding
                filename.replace('%20', ' ')  # Manual space replacement
            ]

            for alt_filename in alternatives:
                alt_path = os.path.join(Config.PROCESSED_FOLDER, alt_filename)
                alt_path = os.path.normpath(alt_path)
                if os.path.exists(alt_path):
                    print(f"Found file using alternative path: {alt_filename}")
                    return send_from_directory(Config.PROCESSED_FOLDER, alt_filename, as_attachment=False)

            return jsonify({'error': f'File not found: {normalized_filename}'}), 404

        # Determine MIME type based on file extension
        file_ext = os.path.splitext(full_path)[1].lower()

        # Set appropriate MIME type and headers
        if file_ext == '.pdf':
            from flask import Response
            try:
                with open(full_path, 'rb') as f:
                    file_data = f.read()

                response = Response(
                    file_data,
                    mimetype='application/pdf',
                    headers={
                        'Content-Disposition': 'inline',
                        'Content-Type': 'application/pdf',
                        'Cache-Control': 'no-cache',
                        'Accept-Ranges': 'bytes',
                        'X-Frame-Options': 'SAMEORIGIN',
                        'X-Content-Type-Options': 'nosniff'
                    }
                )
                print(f"Serving PDF: {os.path.basename(full_path)} ({len(file_data)} bytes)")
                return response
            except Exception as pdf_error:
                print(f"Error reading PDF file: {pdf_error}")
                return jsonify({'error': f'Error reading PDF: {str(pdf_error)}'}), 500
        else:
            # For images and other files, use send_from_directory
            try:
                rel_path = os.path.relpath(full_path, Config.PROCESSED_FOLDER)
                return send_from_directory(Config.PROCESSED_FOLDER, rel_path, as_attachment=False)
            except Exception as send_error:
                print(f"Error with send_from_directory: {send_error}")
                # Fallback: try to serve the file manually
                try:
                    with open(full_path, 'rb') as f:
                        file_data = f.read()

                    # Determine MIME type for images
                    mime_type = 'application/octet-stream'
                    if file_ext in ['.jpg', '.jpeg']:
                        mime_type = 'image/jpeg'
                    elif file_ext == '.png':
                        mime_type = 'image/png'
                    elif file_ext == '.gif':
                        mime_type = 'image/gif'
                    elif file_ext in ['.tiff', '.tif']:
                        mime_type = 'image/tiff'
                    elif file_ext == '.bmp':
                        mime_type = 'image/bmp'

                    from flask import Response
                    response = Response(
                        file_data,
                        mimetype=mime_type,
                        headers={'Content-Disposition': 'inline'}
                    )
                    print(f"Serving {file_ext} file manually: {os.path.basename(full_path)} ({len(file_data)} bytes)")
                    return response
                except Exception as manual_error:
                    print(f"Error serving file manually: {manual_error}")
                    return jsonify({'error': f'Error serving file: {str(manual_error)}'}), 500

    except Exception as e:
        print(f"Preview error: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Preview error: {str(e)}'}), 500

@app.route('/api/preview-files/<session_id>')
def get_preview_files(session_id):
    """Get list of processed files for preview from a session"""
    global processing_status

    try:
        if session_id not in processing_status:
            return jsonify({'error': 'Session not found'}), 404

        status = processing_status[session_id]
        if status['status'] != 'completed':
            return jsonify({'error': 'Processing not completed'}), 400

        print(f"Getting preview files for session: {session_id}")
        print(f"Results count: {len(status['results'])}")

        # Filter for successfully processed files that are PDFs or images
        preview_files = []
        for i, result in enumerate(status['results']):
            if (result['status'] == 'completed' and
                result.get('processed_path') and
                os.path.exists(result['processed_path'])):

                # Check if file is PDF or image
                file_ext = os.path.splitext(result['processed_path'])[1].lower()

                if file_ext in ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                    # Get relative path from processed folder for the preview endpoint
                    rel_path = os.path.relpath(result['processed_path'], Config.PROCESSED_FOLDER)

                    # Verify the relative path works
                    test_full_path = os.path.join(Config.PROCESSED_FOLDER, rel_path)
                    if not os.path.exists(test_full_path):
                        print(f"Warning: Relative path verification failed for {result['original_filename']}")
                        continue

                    preview_files.append({
                        'original_filename': result['original_filename'],
                        'new_filename': result['new_filename'],
                        'processed_path': rel_path,
                        'full_path': result['processed_path'],
                        'document_type': result['document_type'],
                        'client_name': result['client_name'],
                        'tax_year': result['tax_year'],
                        'file_type': 'pdf' if file_ext == '.pdf' else 'image'
                    })

        print(f"Total preview files found: {len(preview_files)}")
        return jsonify({
            'success': True,
            'files': preview_files
        })

    except Exception as e:
        print(f"Error in get_preview_files: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/rename', methods=['POST'])
def rename_file():
    """Rename a processed file"""
    try:
        data = request.json
        old_path = data.get('oldPath', '')
        new_name = data.get('newName', '')

        if not old_path or not new_name:
            return jsonify({
                'success': False,
                'error': 'Both oldPath and newName are required'
            }), 400

        # Remove 'processed/' prefix if present for consistency
        if old_path.startswith('processed/'):
            old_path = old_path[9:]

        # Build full paths
        old_full_path = os.path.join(Config.PROCESSED_FOLDER, old_path)

        # Get directory and build new path
        directory = os.path.dirname(old_full_path)
        new_full_path = os.path.join(directory, new_name)

        # Check if old file exists
        if not os.path.exists(old_full_path):
            return jsonify({
                'success': False,
                'error': 'Original file not found'
            }), 404

        # Check if new filename already exists
        if os.path.exists(new_full_path):
            return jsonify({
                'success': False,
                'error': 'A file with that name already exists'
            }), 400

        # Perform the rename
        os.rename(old_full_path, new_full_path)

        return jsonify({
            'success': True,
            'message': 'File renamed successfully',
            'oldPath': old_path,
            'newPath': os.path.relpath(new_full_path, Config.PROCESSED_FOLDER)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current settings (masked)"""
    try:
        # Check if API key is set and valid
        api_key_configured = bool(Config.ANTHROPIC_API_KEY and Config.ANTHROPIC_API_KEY.strip() != '')

        # Create masked version of API key
        masked_api_key = None
        if api_key_configured:
            key = Config.ANTHROPIC_API_KEY
            if len(key) > 20:
                masked_api_key = key[:15] + '...' + key[-4:]
            else:
                masked_api_key = key[:8] + '...'

        return jsonify({
            'success': True,
            'api_key_configured': api_key_configured,
            'api_key_set': api_key_configured,  # Keep both for compatibility
            'masked_api_key': masked_api_key
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Save settings to .env file"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        api_key = data.get('api_key', '').strip()
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required'
            }), 400

        if not api_key.startswith('sk-ant-api03-'):
            return jsonify({
                'success': False,
                'error': 'Invalid API key format'
            }), 400

        # Update .env file
        env_path = os.path.join(os.getcwd(), '.env')
        env_lines = []
        api_key_found = False

        # Read existing .env file if it exists
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('ANTHROPIC_API_KEY='):
                        env_lines.append(f'ANTHROPIC_API_KEY={api_key}')
                        api_key_found = True
                    elif line and not line.startswith('#'):
                        env_lines.append(line)

        # Add API key if not found
        if not api_key_found:
            env_lines.append(f'ANTHROPIC_API_KEY={api_key}')

        # Write updated .env file
        with open(env_path, 'w') as f:
            for line in env_lines:
                f.write(line + '\n')

        # Update the config object
        Config.ANTHROPIC_API_KEY = api_key

        # Reinitialize processor with new API key
        global processor
        init_processor()

        return jsonify({
            'success': True,
            'message': 'Settings saved successfully'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large'}), 413

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/processor-status')
def processor_status():
    """Get processor initialization status"""
    global processor, processor_initializing

    if processor_initializing:
        return jsonify({
            'status': 'initializing',
            'message': 'AI models are loading, please wait...'
        })
    elif processor:
        return jsonify({
            'status': 'ready',
            'message': 'Ready to process documents'
        })
    else:
        return jsonify({
            'status': 'unavailable',
            'message': 'Document processing unavailable. Check API key configuration.'
        })

@app.route('/favicon.ico')
def favicon():
    """Serve favicon to prevent 404 errors"""
    return '', 204

def is_port_in_use(port):
    """Check if a port is in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('', port))
            return False
        except OSError:
            return True

if __name__ == '__main__':
    # Initialize processor
    if init_processor():
        print("Starting Tax Document Sorter...")

        # Use port 8000 consistently
        port = 8000
        if is_port_in_use(port):
            print(f"Port {port} is in use. Please stop any other applications using port {port} and try again.")
            print("Alternatively, you can kill the process using:")
            print(f"  lsof -ti:{port} | xargs kill -9")
            exit(1)
        else:
            print(f"Starting on port {port}")
            print(f"Access the application at: http://localhost:{port}")

        app.run(debug=False, host='0.0.0.0', port=port)
    else:
        print("Failed to initialize. Please check your configuration and API keys.")