from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import uuid
from werkzeug.utils import secure_filename
import threading
import time
import shutil
from pathlib import Path
import logging
from config import Config
from utils.enhanced_file_processor import EnhancedTaxDocumentProcessor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Global variables for processing
processing_sessions = {}
enhanced_processor = None

def init_enhanced_processor():
    """Initialize the enhanced document processor"""
    global enhanced_processor
    if not Config.ANTHROPIC_API_KEY or Config.ANTHROPIC_API_KEY.strip() == '':
        print("Warning: ANTHROPIC_API_KEY not set. Document processing will be limited.")
        enhanced_processor = None
        return True
    
    try:
        enhanced_processor = EnhancedTaxDocumentProcessor(
            donut_model_path=Config.DONUT_MODEL_PATH,
            claude_api_key=Config.ANTHROPIC_API_KEY
        )
        print("Enhanced document processor initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing enhanced processor: {e}")
        enhanced_processor = None
        return True  # Allow app to start even if processor fails

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def process_documents_enhanced(session_id, file_paths, processing_options):
    """Enhanced background function to process documents with comprehensive analysis"""
    global processing_sessions, enhanced_processor
    
    if not enhanced_processor:
        processing_sessions[session_id]['status'] = 'error'
        processing_sessions[session_id]['error'] = 'Enhanced document processor not initialized'
        return
    
    try:
        total_files = len(file_paths)
        session = processing_sessions[session_id]
        
        session.update({
            'total': total_files,
            'results': [],
            'enhanced_stats': {},
            'processing_start_time': time.time()
        })
        
        # Initialize all files with "waiting" status
        for _, original_filename in file_paths:
            session['results'].append({
                'original_filename': original_filename,
                'status': 'waiting',
                'client_name': None,
                'document_type': None,
                'tax_year': None,
                'new_filename': None,
                'error': None,
                'confidence': 0.0,
                'entity_info': {},
                'extracted_details': {},
                'processing_notes': []
            })
        
        # Get processing options
        manual_client_info = processing_options.get('manual_client_info')
        
        # Process each document with enhanced capabilities
        for i, (file_path, original_filename) in enumerate(file_paths):
            # Update progress
            session['current'] = i + 1
            session['current_file'] = original_filename
            session['results'][i]['status'] = 'processing'
            
            try:
                # Enhanced processing with comprehensive extraction
                result = enhanced_processor.process_document(
                    file_path, original_filename, manual_client_info
                )
                
                # Update the result in the session
                session['results'][i] = result
                
                # Add processing timestamp
                session['results'][i]['processed_at'] = time.time()
                
                logging.info(f"Enhanced processing completed for {original_filename}")
                
            except Exception as e:
                logging.error(f"Error processing {original_filename}: {e}")
                session['results'][i].update({
                    'status': 'error',
                    'error': str(e),
                    'processed_at': time.time()
                })
            
            # Clean up uploaded file
            try:
                os.remove(file_path)
            except:
                pass
        
        # Generate enhanced statistics
        session['enhanced_stats'] = enhanced_processor.get_enhanced_processing_stats(
            session['results']
        )
        
        session.update({
            'status': 'completed',
            'processing_end_time': time.time(),
            'total_processing_time': time.time() - session['processing_start_time']
        })
        
        logging.info(f"Batch processing completed for session {session_id}")
        
    except Exception as e:
        logging.error(f"Critical error in enhanced processing: {e}")
        session.update({
            'status': 'error',
            'error': str(e),
            'processing_end_time': time.time()
        })

@app.route('/')
def index():
    """Main page with modern enhanced upload interface"""
    return render_template('modern_enhanced_index.html')

@app.route('/legacy')
def legacy_index():
    """Legacy enhanced interface for backward compatibility"""
    return render_template('enhanced_index.html')

@app.route('/enhanced_process', methods=['POST'])
@app.route('/upload', methods=['POST'])
def upload_files_enhanced():
    """Handle file upload with enhanced processing options"""
    global processing_sessions
    
    if not enhanced_processor:
        return jsonify({
            'success': False,
            'error': 'Enhanced document processor not initialized. Please set your Claude API key in Settings.',
            'message': 'Claude API key required'
        }), 500
    
    # Check if files were uploaded
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'No files uploaded', 'message': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'success': False, 'error': 'No files selected', 'message': 'No files selected'}), 400
    
    # Get enhanced processing options
    processing_mode = request.form.get('processing_mode', 'auto')
    entity_detection = request.form.get('entity_detection', 'enabled') == 'enabled'
    filename_templates = request.form.get('filename_templates', 'smart')
    
    manual_client_info = None
    if processing_mode == 'manual':
        first_name = request.form.get('client_first_name', '').strip()
        last_name = request.form.get('client_last_name', '').strip()
        
        if not first_name or not last_name:
            return jsonify({
                'success': False,
                'error': 'First name and last name required for manual mode',
                'message': 'Client names required'
            }), 400
        
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
        return jsonify({'success': False, 'error': 'No valid files uploaded', 'message': 'No valid files uploaded'}), 400
    
    # Initialize enhanced processing session
    processing_sessions[session_id] = {
        'status': 'processing',
        'total': len(file_paths),
        'current': 0,
        'current_file': '',
        'results': [],
        'enhanced_stats': {},
        'error': None,
        'processing_options': {
            'processing_mode': processing_mode,
            'entity_detection': entity_detection,
            'filename_templates': filename_templates,
            'manual_client_info': manual_client_info
        },
        'session_created_at': time.time()
    }
    
    # Start enhanced background processing
    thread = threading.Thread(
        target=process_documents_enhanced,
        args=(session_id, file_paths, processing_sessions[session_id]['processing_options'])
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'job_id': session_id,
        'message': 'Processing started successfully'
    })

@app.route('/enhanced_status/<session_id>')
@app.route('/status/<session_id>')
def get_enhanced_status(session_id):
    """Get enhanced processing status for a session"""
    global processing_sessions
    
    if session_id not in processing_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = processing_sessions[session_id]
    
    # Calculate progress percentage
    progress_percentage = 0
    if session.get('total', 0) > 0:
        progress_percentage = (session.get('current', 0) / session['total']) * 100
    
    # Build response data for modern interface compatibility
    response_data = {
        'status': session['status'],
        'progress': progress_percentage,
        'current_file': session.get('current_file', ''),
        'current': session.get('current', 0),
        'total': session.get('total', 0),
        'results': session.get('results', []),
        'error': session.get('error'),
        'message': session.get('error') or f"Processing {session.get('current', 0)}/{session.get('total', 0)} files"
    }
    
    # Add timing information
    if session.get('processing_start_time'):
        response_data['elapsed_time'] = time.time() - session['processing_start_time']
    
    # Add processed files information for file explorer
    if session['status'] == 'completed':
        response_data['preview_stats'] = _generate_preview_stats(session['results'])
        response_data['processed_files'] = []
        
        # Extract processed file information
        for result in session.get('results', []):
            if result['status'] == 'completed' and result.get('new_filename'):
                response_data['processed_files'].append({
                    'name': result.get('new_filename'),
                    'path': result.get('output_path', ''),
                    'original_name': result.get('original_filename')
                })
    
    return jsonify(response_data)

@app.route('/results/<session_id>')
def get_enhanced_results(session_id):
    """Get enhanced processing results for a session"""
    global processing_sessions
    
    if session_id not in processing_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = processing_sessions[session_id]
    if session['status'] != 'completed':
        return jsonify({'error': 'Processing not completed'}), 400
    
    return jsonify({
        'results': session['results'],
        'enhanced_stats': session['enhanced_stats'],
        'processing_summary': {
            'total_processing_time': session.get('total_processing_time', 0),
            'files_processed': len(session['results']),
            'successful_extractions': len([r for r in session['results'] if r['status'] == 'completed']),
            'errors': len([r for r in session['results'] if r['status'] == 'error'])
        }
    })

@app.route('/preview/<session_id>')
def get_processing_preview(session_id):
    """Get real-time preview of processing results"""
    global processing_sessions
    
    if session_id not in processing_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = processing_sessions[session_id]
    
    # Generate preview for completed files
    preview_results = []
    for result in session.get('results', []):
        if result['status'] == 'completed':
            preview = {
                'original_filename': result['original_filename'],
                'new_filename': result.get('new_filename'),
                'client_name': result.get('client_name'),
                'document_type': result.get('document_type'),
                'tax_year': result.get('tax_year'),
                'confidence': result.get('confidence', 0),
                'entity_type': result.get('entity_info', {}).get('entity_type'),
                'processing_notes': result.get('processing_notes', [])
            }
            preview_results.append(preview)
    
    return jsonify({
        'preview_results': preview_results,
        'processing_status': session['status'],
        'progress': {
            'current': session.get('current', 0),
            'total': session.get('total', 0),
            'current_file': session.get('current_file', '')
        }
    })

def _generate_preview_stats(results):
    """Generate quick preview statistics"""
    if not results:
        return {}
    
    completed_results = [r for r in results if r['status'] == 'completed']
    
    entity_types = {}
    document_types = {}
    confidence_levels = {'high': 0, 'medium': 0, 'low': 0}
    
    for result in completed_results:
        # Entity types
        entity_type = result.get('entity_info', {}).get('entity_type', 'Unknown')
        entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        
        # Document types
        doc_type = result.get('document_type', 'Unknown')
        document_types[doc_type] = document_types.get(doc_type, 0) + 1
        
        # Confidence levels
        confidence = result.get('confidence', 0)
        if confidence > 0.8:
            confidence_levels['high'] += 1
        elif confidence > 0.5:
            confidence_levels['medium'] += 1
        else:
            confidence_levels['low'] += 1
    
    return {
        'total_completed': len(completed_results),
        'total_errors': len([r for r in results if r['status'] == 'error']),
        'entity_types': entity_types,
        'document_types': document_types,
        'confidence_levels': confidence_levels
    }

# Directory management API (enhanced)
@app.route('/api/directory')
@app.route('/api/directory/')
@app.route('/api/directory/<path:dir_path>')
def get_directory_contents_enhanced(dir_path=''):
    """Enhanced directory contents with metadata"""
    try:
        # Build full path
        if not dir_path or dir_path == 'processed':
            full_path = Config.PROCESSED_FOLDER
            relative_path = 'processed'
        else:
            if dir_path.startswith('processed/'):
                dir_path = dir_path[10:]
            full_path = os.path.join(Config.PROCESSED_FOLDER, dir_path)
            relative_path = f"processed/{dir_path}" if dir_path else 'processed'
        
        if not os.path.exists(full_path):
            os.makedirs(full_path, exist_ok=True)
        
        # Get directory contents with metadata
        dirs = []
        files = []
        
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            if os.path.isdir(item_path):
                # Count files in directory
                try:
                    file_count = len([f for f in os.listdir(item_path) 
                                    if os.path.isfile(os.path.join(item_path, f))])
                    dirs.append({
                        'name': item,
                        'file_count': file_count
                    })
                except:
                    dirs.append({
                        'name': item,
                        'file_count': 0
                    })
            else:
                # Get file metadata
                try:
                    stat = os.stat(item_path)
                    files.append({
                        'name': item,
                        'size': stat.st_size,
                        'modified': stat.st_mtime
                    })
                except:
                    files.append({
                        'name': item,
                        'size': 0,
                        'modified': 0
                    })
        
        return jsonify({
            'success': True,
            'fullPath': full_path,
            'relativePath': relative_path,
            'dirs': sorted(dirs, key=lambda x: x['name']),
            'files': sorted(files, key=lambda x: x['name']),
            'total_dirs': len(dirs),
            'total_files': len(files)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Settings API (enhanced)
@app.route('/api/settings', methods=['GET'])
def get_enhanced_settings():
    """Get enhanced application settings"""
    return jsonify({
        'claude_api_configured': bool(Config.ANTHROPIC_API_KEY),
        'donut_model_path': Config.DONUT_MODEL_PATH,
        'processing_capabilities': {
            'enhanced_ocr': bool(enhanced_processor),
            'entity_recognition': True,
            'smart_filename_generation': True,
            'multi_document_types': True
        },
        'supported_document_types': [
            'Form 1040', 'Form W-2', 'Form 1099 (all variants)',
            'Schedule K-1', 'Form 1098', 'Form W-9',
            'State Tax Forms', 'Property Tax Statements'
        ],
        'entity_types_supported': [
            'Individual', 'LLC', 'Corporation', 'Partnership',
            'Trust', 'Estate', 'S-Corporation'
        ],
        'max_file_size_mb': Config.MAX_FILE_SIZE // (1024 * 1024),
        'allowed_extensions': list(Config.ALLOWED_EXTENSIONS)
    })

@app.route('/api/settings', methods=['POST'])
def save_enhanced_settings():
    """Save enhanced application settings"""
    try:
        data = request.get_json()
        
        # Update Claude API key if provided
        if 'claude_api_key' in data:
            new_api_key = data['claude_api_key'].strip()
            if new_api_key:
                # Test the API key
                try:
                    test_processor = EnhancedTaxDocumentProcessor(
                        donut_model_path=Config.DONUT_MODEL_PATH,
                        claude_api_key=new_api_key
                    )
                    # If successful, update global processor
                    global enhanced_processor
                    enhanced_processor = test_processor
                    Config.ANTHROPIC_API_KEY = new_api_key
                    
                    # Update environment variable for persistence
                    os.environ['ANTHROPIC_API_KEY'] = new_api_key
                    
                except Exception as e:
                    return jsonify({
                        'success': False,
                        'error': f'Invalid Claude API key: {str(e)}'
                    }), 400
        
        return jsonify({
            'success': True,
            'message': 'Settings updated successfully',
            'processor_status': 'active' if enhanced_processor else 'inactive'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large'}), 413

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Resource not found'}), 404

# Health check endpoint
@app.route('/api/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'processor_status': 'active' if enhanced_processor else 'inactive',
        'timestamp': time.time()
    })

# Legacy compatibility routes
@app.route('/upload_legacy', methods=['POST'])
def upload_files_legacy():
    """Legacy upload endpoint for backward compatibility"""
    # Convert to enhanced format and process
    response = upload_files_enhanced()
    return response

if __name__ == '__main__':
    # Initialize enhanced processor on startup
    init_enhanced_processor()
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=8080) 