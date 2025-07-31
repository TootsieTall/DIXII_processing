from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
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
from utils.intelligent_batch_processor import ProcessingPriority
import json
import traceback
import zipfile
import io
from datetime import datetime

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

def cleanup_old_uploads(max_age_hours=24):
    """Clean up old files from uploads folder"""
    try:
        upload_folder = Config.UPLOAD_FOLDER
        if not os.path.exists(upload_folder):
            return
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for filename in os.listdir(upload_folder):
            file_path = os.path.join(upload_folder, filename)
            
            # Skip .gitkeep and other system files
            if filename in ['.gitkeep', '.DS_Store']:
                continue
                
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getmtime(file_path)
                if file_age > max_age_seconds:
                    try:
                        os.remove(file_path)
                        logging.info(f"Cleaned up old upload file: {filename}")
                    except Exception as e:
                        logging.warning(f"Failed to clean up {filename}: {e}")
                        
    except Exception as e:
        logging.error(f"Error during upload cleanup: {e}")

def cleanup_old_sessions(max_age_hours=2):
    """Clean up old processing sessions from memory"""
    global processing_sessions
    
    try:
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        sessions_to_remove = []
        
        for session_id, session in processing_sessions.items():
            # Check if session is old enough to be cleaned up
            session_age = current_time - session.get('session_created_at', current_time)
            
            # Clean up sessions that are:
            # 1. Completed/Error and older than max_age_hours
            # 2. Stuck in processing for more than STUCK_SESSION_CLEANUP_AGE_HOURS
            if (session['status'] in ['completed', 'error'] and session_age > max_age_seconds) or \
               (session['status'] == 'processing' and session_age > Config.STUCK_SESSION_CLEANUP_AGE_HOURS * 3600):
                sessions_to_remove.append(session_id)
                logging.info(f"Marking session {session_id} for cleanup (age: {session_age/3600:.1f}h, status: {session['status']})")
        
        # Remove old sessions
        for session_id in sessions_to_remove:
            del processing_sessions[session_id]
            logging.info(f"Cleaned up old session: {session_id}")
            
    except Exception as e:
        logging.error(f"Error during session cleanup: {e}")

def _update_batch_progress(session_id, current, filename):
    """Update batch processing progress for real-time updates"""
    global processing_sessions
    
    if session_id in processing_sessions:
        session = processing_sessions[session_id]
        session['current'] = current
        session['current_file'] = filename
        
        # Update the corresponding result status
        if current > 0 and current <= len(session['results']):
            session['results'][current - 1]['status'] = 'processing'
        
        logging.info(f"Batch progress update: {current}/{session.get('total', 0)} - {filename}")
        logging.info(f"Session {session_id} batch processing file {current}/{session.get('total', 0)}: {filename}")

def init_enhanced_processor():
    """Initialize the enhanced document processor with batch processing"""
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
        print("Enhanced document processor with intelligent batch processing initialized successfully")
        return True
    except Exception as e:
        print(f"Error initializing enhanced processor: {e}")
        enhanced_processor = None
        return True  # Allow app to start even if processor fails

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def process_documents_enhanced_with_batching(session_id, file_paths, processing_options):
    """Enhanced background function with intelligent batch processing"""
    global processing_sessions, enhanced_processor
    
    if not enhanced_processor:
        processing_sessions[session_id]['status'] = 'error'
        processing_sessions[session_id]['error'] = 'Enhanced document processor not initialized'
        return
    
    try:
        total_files = len(file_paths)
        session = processing_sessions[session_id]
        
        # Initialize results array if not already done
        if not session.get('results'):
            session['results'] = []
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
                    'processing_notes': [],
                    'processing_mode': 'unknown',
                    'batch_performance': {}
                })
        
        session.update({
            'total': total_files,
            'enhanced_stats': {},
            'batch_stats': {}
        })
        
        # Set processing start time if not already set
        if not session.get('processing_start_time'):
            session['processing_start_time'] = time.time()
        
        # Get processing options
        manual_client_info = processing_options.get('manual_client_info')
        batch_processing = processing_options.get('batch_processing', True)
        
        # Phase 6: Use intelligent batch processing
        if batch_processing and total_files >= 2:
            # Use batch processing for multiple documents
            session['processing_mode'] = 'intelligent_batch'
            file_paths_and_names = [(fp, fn) for fp, fn in file_paths]
            
            # Configure batch processing options
            batch_options = {
                'manual_client_info': manual_client_info,
                'high_priority': processing_options.get('high_priority', False),
                'session_callback': lambda current, filename: _update_batch_progress(session_id, current, filename)
            }
            
            # Process with intelligent batching
            results = enhanced_processor.process_document_batch(file_paths_and_names, batch_options)
            
            # Update session results with proper validation
            if results and isinstance(results, list):
                for i, result in enumerate(results):
                    if i < len(session['results']):
                        # Ensure result has required fields
                        if isinstance(result, dict):
                            session['results'][i].update(result)
                            session['results'][i]['processed_at'] = time.time()
                        else:
                            logging.error(f"Invalid result format at index {i}: {result}")
                            session['results'][i].update({
                                'status': 'error',
                                'error': 'Invalid result format',
                                'processed_at': time.time()
                            })
            else:
                logging.error(f"Invalid batch processing results: {results}")
                # Mark all results as error
                for i in range(len(session['results'])):
                    session['results'][i].update({
                        'status': 'error',
                        'error': 'Batch processing failed',
                        'processed_at': time.time()
                    })
            
        else:
            # Fall back to individual processing
            session['processing_mode'] = 'individual_processing'
            
            for i, (file_path, original_filename) in enumerate(file_paths):
                # Update progress
                session['current'] = i + 1
                session['current_file'] = original_filename
                session['results'][i]['status'] = 'processing'
                
                logging.info(f"Starting processing file {i+1}/{len(file_paths)}: {original_filename}")
                
                # Small delay to ensure progress is visible during testing
                time.sleep(0.1)
                
                try:
                    # Determine processing priority
                    priority = ProcessingPriority.HIGH if processing_options.get('high_priority') else ProcessingPriority.NORMAL
                    
                    # Enhanced processing with batch consideration
                    result = enhanced_processor.process_document_with_batching(
                        file_path, original_filename, priority, manual_client_info
                    )
                    
                    # Update the result in the session with validation
                    if isinstance(result, dict):
                        session['results'][i].update(result)
                        session['results'][i]['processed_at'] = time.time()
                    else:
                        logging.error(f"Invalid result format for {original_filename}: {result}")
                        session['results'][i].update({
                            'status': 'error',
                            'error': 'Invalid result format',
                            'processed_at': time.time()
                        })
                    
                    logging.info(f"Enhanced processing completed for {original_filename}")
                    
                except Exception as e:
                    logging.error(f"Error processing {original_filename}: {e}")
                    session['results'][i].update({
                        'status': 'error',
                        'error': str(e),
                        'processed_at': time.time(),
                        'processing_mode': 'individual_error'
                    })
                
                # Clean up uploaded file
                try:
                    os.remove(file_path)
                except:
                    pass
        
        # Generate enhanced statistics including batch performance
        try:
            session['enhanced_stats'] = enhanced_processor.get_enhanced_processing_stats(
                session['results']
            )
        except Exception as e:
            logging.error(f"Error generating enhanced stats: {e}")
            session['enhanced_stats'] = {}
        
        # Get batch processing specific statistics
        try:
            session['batch_stats'] = enhanced_processor.get_batch_processing_status()
        except Exception as e:
            logging.error(f"Error getting batch stats: {e}")
            session['batch_stats'] = {}
        
        session.update({
            'status': 'completed',
            'current': len(file_paths),  # Ensure current shows total when complete
            'current_file': '',  # Clear current file when done
            'processing_end_time': time.time(),
            'total_processing_time': time.time() - session['processing_start_time']
        })
        
        # Clean up all uploaded files after processing completion
        for file_path, _ in file_paths:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"Cleaned up processed file: {file_path}")
            except Exception as e:
                logging.warning(f"Failed to clean up {file_path}: {e}")
        
        logging.info(f"Batch processing completed for session {session_id} in {session['processing_mode']} mode")
        
    except Exception as e:
        logging.error(f"Critical error in batch processing for session {session_id}: {e}")
        session.update({
            'status': 'error',
            'error': str(e),
            'processing_end_time': time.time()
        })

@app.route('/')
def index():
    """Main page with enhanced tax document processing interface"""
    return render_template('modern_enhanced_index.html')

@app.route('/enhanced_process', methods=['POST'])
@app.route('/upload', methods=['POST'])
def upload_files_enhanced():
    """Handle file upload with enhanced processing including intelligent batch processing"""
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
    
    # Phase 6: Batch processing options
    batch_processing = request.form.get('batch_processing', 'enabled') == 'enabled'
    high_priority = request.form.get('high_priority', 'false') == 'true'
    
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
    
    # Clean up old uploads and sessions before processing new ones
    if Config.ENABLE_UPLOAD_CLEANUP:
        cleanup_old_uploads(max_age_hours=Config.UPLOAD_CLEANUP_AGE_HOURS)
    if Config.ENABLE_SESSION_CLEANUP:
        cleanup_old_sessions(max_age_hours=Config.SESSION_CLEANUP_AGE_HOURS)
    
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
    
    # Initialize enhanced processing session with batch processing support
    processing_sessions[session_id] = {
        'status': 'processing',
        'total': len(file_paths),
        'current': 0,
        'current_file': '',
        'results': [{'original_filename': filename, 'status': 'waiting'} for _, filename in file_paths],
        'enhanced_stats': {},
        'batch_stats': {},
        'error': None,
        'processing_mode': 'unknown',
        'processing_start_time': time.time(),
        'processing_options': {
            'processing_mode': processing_mode,
            'entity_detection': entity_detection,
            'filename_templates': filename_templates,
            'manual_client_info': manual_client_info,
            'batch_processing': batch_processing,
            'high_priority': high_priority
        },
        'session_created_at': time.time()
    }
    
    # Start enhanced background processing with batch support
    thread = threading.Thread(
        target=process_documents_enhanced_with_batching,
        args=(session_id, file_paths, processing_sessions[session_id]['processing_options'])
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'job_id': session_id,
        'message': 'Processing started with intelligent batch optimization',
        'batch_processing_enabled': batch_processing,
        'estimated_batch_savings': '10-25% cost reduction, 15-30% time savings' if batch_processing and len(file_paths) >= 2 else None
    })

# Update the existing status endpoint to include batch information
@app.route('/status/<session_id>')
def get_status(session_id):
    """Get processing status with batch processing information"""
    global processing_sessions
    
    # Clean up old sessions before checking status
    if Config.ENABLE_SESSION_CLEANUP:
        cleanup_old_sessions(max_age_hours=Config.SESSION_CLEANUP_AGE_HOURS)
    
    if session_id not in processing_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = processing_sessions[session_id]
    
    response = {
        'status': session['status'],
        'total': session['total'],
        'current': session.get('current', 0),
        'current_file': session.get('current_file', ''),
        'results': session['results'],
        'enhanced_stats': session.get('enhanced_stats', {}),
        'batch_stats': session.get('batch_stats', {}),  # Include batch statistics
        'processing_mode': session.get('processing_mode', 'unknown'),
        'error': session.get('error')
    }
    
    # Calculate processing time
    if session.get('processing_start_time'):
        if session['status'] == 'completed':
            response['processing_time'] = session.get('processing_end_time', time.time()) - session['processing_start_time']
        else:
            response['processing_time'] = time.time() - session['processing_start_time']
    
    return jsonify(response)

@app.route('/enhanced_status/<session_id>')
def get_enhanced_status(session_id):
    """Get enhanced processing status for a session"""
    global processing_sessions
    
    # Clean up old sessions before checking status
    if Config.ENABLE_SESSION_CLEANUP:
        cleanup_old_sessions(max_age_hours=Config.SESSION_CLEANUP_AGE_HOURS)
    
    # If session doesn't exist, return a more helpful error
    if session_id not in processing_sessions:
        return jsonify({
            'error': 'Session not found', 
            'message': 'This processing session has expired or was not found. Please upload your files again.',
            'session_id': session_id,
            'available_sessions': list(processing_sessions.keys())
        }), 404
    
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

# File serving and document viewing routes
@app.route('/processed/<path:filename>')
def serve_processed_file(filename):
    """Serve processed files for viewing and download"""
    try:
        # Security: prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            logging.warning(f"Invalid file path requested: {filename}")
            return "Invalid file path", 400
        
        full_path = os.path.join(Config.PROCESSED_FOLDER, filename)
        logging.info(f"Serving processed file: {filename} from {full_path}")
        
        if not os.path.exists(full_path):
            logging.error(f"File not found: {full_path}")
            return "File not found", 404
        
        return send_from_directory(Config.PROCESSED_FOLDER, filename, as_attachment=False)
    except Exception as e:
        logging.error(f"Error serving file {filename}: {e}")
        return f"Error serving file: {e}", 500

@app.route('/download/<path:filename>')
def download_processed_file(filename):
    """Download processed files"""
    try:
        # Security: prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            return "Invalid file path", 400
        
        return send_from_directory(Config.PROCESSED_FOLDER, filename, as_attachment=True)
    except FileNotFoundError:
        return "File not found", 404

# File Management APIs (NEW)
@app.route('/api/rename_file', methods=['POST'])
def rename_file():
    """Rename a processed file"""
    try:
        data = request.get_json()
        old_path = data.get('old_path', '').strip()
        new_filename = data.get('new_filename', '').strip()
        
        if not old_path or not new_filename:
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        # Security: prevent directory traversal
        if '..' in old_path or old_path.startswith('/') or '..' in new_filename:
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400
        
        # Build full paths
        old_full_path = os.path.join(Config.PROCESSED_FOLDER, old_path)
        
        # Extract directory and create new path
        old_dir = os.path.dirname(old_full_path)
        new_full_path = os.path.join(old_dir, new_filename)
        
        # Check if old file exists
        if not os.path.exists(old_full_path):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Check if new filename already exists
        if os.path.exists(new_full_path):
            return jsonify({'success': False, 'error': 'A file with that name already exists'}), 409
        
        # Perform rename
        os.rename(old_full_path, new_full_path)
        
        # Return new path
        new_relative_path = os.path.relpath(new_full_path, Config.PROCESSED_FOLDER)
        
        return jsonify({
            'success': True,
            'message': 'File renamed successfully',
            'new_path': new_relative_path.replace('\\', '/'),  # Normalize path separators
            'new_filename': new_filename
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/edit_metadata', methods=['POST'])
def edit_file_metadata():
    """Edit file metadata and optionally rename based on new metadata"""
    try:
        data = request.get_json()
        file_path = data.get('file_path', '').strip()
        
        if not file_path:
            return jsonify({'success': False, 'error': 'Missing file path'}), 400
        
        # Security: prevent directory traversal
        if '..' in file_path or file_path.startswith('/'):
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400
        
        # Get metadata updates
        new_client_name = data.get('client_name', '').strip()
        new_document_type = data.get('document_type', '').strip()
        new_tax_year = data.get('tax_year', '').strip()
        auto_rename = data.get('auto_rename', False)
        
        # Build full path
        full_path = os.path.join(Config.PROCESSED_FOLDER, file_path)
        
        # Check if file exists
        if not os.path.exists(full_path):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        response_data = {
            'success': True,
            'message': 'Metadata updated successfully',
            'updated_fields': [],
            'suggestions': {}
        }
        
        # If auto_rename is requested, generate new filename
        if auto_rename and enhanced_processor:
            try:
                # Create mock extracted info for filename generation
                extracted_info = {
                    'document_type': new_document_type or 'Unknown Document',
                    'tax_year': new_tax_year or 'Unknown_Year',
                    'confidence': 0.9  # High confidence for manual input
                }
                
                # Create mock entity info
                if new_client_name:
                    name_parts = new_client_name.split()
                    if len(name_parts) >= 2:
                        entity_info = {
                            'entity_type': 'Individual',
                            'final_folder': new_client_name.replace(' ', '_'),
                            'is_joint': False
                        }
                        extracted_info.update({
                            'person_first_name': name_parts[0],
                            'person_last_name': ' '.join(name_parts[1:])
                        })
                    else:
                        entity_info = {
                            'entity_type': 'Business',
                            'final_folder': new_client_name.replace(' ', '_'),
                            'business_name': new_client_name
                        }
                else:
                    entity_info = {
                        'entity_type': 'Individual',
                        'final_folder': 'Unknown_Client'
                    }
                
                # Generate new filename
                original_filename = os.path.basename(full_path)
                filename_info = enhanced_processor.filename_generator.get_filename_preview(
                    extracted_info, entity_info, original_filename
                )
                
                suggested_filename = filename_info['filename']
                
                # Check if filename would actually change
                if suggested_filename != original_filename:
                    response_data['suggestions']['filename'] = suggested_filename
                    response_data['suggestions']['explanation'] = filename_info.get('explanation', '')
                    
            except Exception as e:
                logging.error(f"Error generating filename suggestion: {e}")
                response_data['suggestions']['error'] = 'Could not generate filename suggestion'
        
        # Add updated fields to response
        if new_client_name:
            response_data['updated_fields'].append('client_name')
        if new_document_type:
            response_data['updated_fields'].append('document_type')
        if new_tax_year:
            response_data['updated_fields'].append('tax_year')
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/move_to_client', methods=['POST'])
def move_file_to_client():
    """Move file to a different client folder"""
    try:
        data = request.get_json()
        file_path = data.get('file_path', '').strip()
        new_client_name = data.get('client_name', '').strip()
        
        if not file_path or not new_client_name:
            return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
        
        # Security: prevent directory traversal
        if '..' in file_path or file_path.startswith('/'):
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400
        
        # Build paths
        old_full_path = os.path.join(Config.PROCESSED_FOLDER, file_path)
        new_client_folder = new_client_name.replace(' ', '_')
        new_client_path = os.path.join(Config.PROCESSED_FOLDER, new_client_folder)
        
        # Check if old file exists
        if not os.path.exists(old_full_path):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Create new client folder if it doesn't exist
        os.makedirs(new_client_path, exist_ok=True)
        
        # Get filename
        filename = os.path.basename(old_full_path)
        new_full_path = os.path.join(new_client_path, filename)
        
        # Check for conflicts
        if os.path.exists(new_full_path):
            # Generate unique filename
            base_name = os.path.splitext(filename)[0]
            extension = os.path.splitext(filename)[1]
            counter = 1
            while os.path.exists(new_full_path):
                new_filename = f"{base_name}_{counter:02d}{extension}"
                new_full_path = os.path.join(new_client_path, new_filename)
                counter += 1
                if counter > 99:
                    return jsonify({'success': False, 'error': 'Too many filename conflicts'}), 409
            filename = new_filename
        
        # Move file
        shutil.move(old_full_path, new_full_path)
        
        # Clean up old folder if empty
        old_folder = os.path.dirname(old_full_path)
        try:
            if old_folder != Config.PROCESSED_FOLDER and not os.listdir(old_folder):
                os.rmdir(old_folder)
        except:
            pass  # Ignore cleanup errors
        
        # Return new path
        new_relative_path = os.path.relpath(new_full_path, Config.PROCESSED_FOLDER)
        
        return jsonify({
            'success': True,
            'message': f'File moved to {new_client_name}',
            'new_path': new_relative_path.replace('\\', '/'),
            'new_client': new_client_name,
            'filename': filename
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reprocess_file', methods=['POST'])
def reprocess_file():
    """Reprocess a file with corrected information"""
    try:
        data = request.get_json()
        file_path = data.get('file_path', '').strip()
        
        if not file_path:
            return jsonify({'success': False, 'error': 'Missing file path'}), 400
        
        if not enhanced_processor:
            return jsonify({'success': False, 'error': 'Enhanced processor not available'}), 500
        
        # Security: prevent directory traversal
        if '..' in file_path or file_path.startswith('/'):
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400
        
        # Build full path
        full_path = os.path.join(Config.PROCESSED_FOLDER, file_path)
        
        # Check if file exists
        if not os.path.exists(full_path):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Get correction parameters
        corrections = data.get('corrections', {})
        manual_client_info = None
        
        if 'client_first_name' in corrections and 'client_last_name' in corrections:
            manual_client_info = {
                'first_name': corrections['client_first_name'].strip(),
                'last_name': corrections['client_last_name'].strip()
            }
        
        # Create a temporary copy for reprocessing
        temp_path = f"temp_reprocess_{uuid.uuid4()}.pdf"
        shutil.copy2(full_path, temp_path)
        
        try:
            # Reprocess the document
            original_filename = os.path.basename(full_path)
            result = enhanced_processor.process_document(
                temp_path, original_filename, manual_client_info
            )
            
            if result['status'] == 'completed':
                # If reprocessing was successful and generated a different result,
                # optionally move/rename the original file
                response_data = {
                    'success': True,
                    'message': 'File reprocessed successfully',
                    'result': {
                        'client_name': result.get('client_name'),
                        'document_type': result.get('document_type'),
                        'tax_year': result.get('tax_year'),
                        'confidence': result.get('confidence'),
                        'new_filename': result.get('new_filename'),
                        'processed_path': result.get('processed_path')
                    }
                }
                
                # Remove original if a new file was created in a different location
                if result.get('processed_path') and result['processed_path'] != full_path:
                    try:
                        os.remove(full_path)
                        response_data['original_removed'] = True
                    except:
                        response_data['original_removed'] = False
                
                return jsonify(response_data)
            else:
                return jsonify({
                    'success': False,
                    'error': f"Reprocessing failed: {result.get('error', 'Unknown error')}"
                }), 500
                
        finally:
            # Clean up temp file
            try:
                os.remove(temp_path)
            except:
                pass
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/files')
def list_all_processed_files():
    """Get comprehensive list of all processed files with metadata"""
    try:
        files = []
        processed_path = Path(Config.PROCESSED_FOLDER)
        
        for client_dir in processed_path.iterdir():
            if client_dir.is_dir() and client_dir.name != '.gitkeep':
                client_files = []
                for file in client_dir.iterdir():
                    if file.is_file():
                        stat = file.stat()
                        client_files.append({
                            'name': file.name,
                            'path': str(file.relative_to(processed_path)),
                            'size': stat.st_size,
                            'modified': stat.st_mtime,
                            'client': client_dir.name
                        })
                
                if client_files:
                    files.append({
                        'client': client_dir.name,
                        'files': client_files,
                        'file_count': len(client_files)
                    })
        
        return jsonify({
            'success': True,
            'clients': files,
            'total_clients': len(files),
            'total_files': sum(client['file_count'] for client in files)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download-all', methods=['GET'])
def download_all_files():
    """Create and download a ZIP file containing all processed files"""
    try:
        processed_path = Path(Config.PROCESSED_FOLDER)
        if not processed_path.exists():
            return jsonify({"error": "No processed files found"}), 404
        
        # Create in-memory ZIP file
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            file_count = 0
            
            # Walk through all files in processed folder
            for root, dirs, files in os.walk(processed_path):
                for file in files:
                    if file != '.gitkeep':  # Skip gitkeep files
                        file_path = Path(root) / file
                        # Create archive path relative to processed folder
                        archive_path = file_path.relative_to(processed_path)
                        zf.write(file_path, archive_path)
                        file_count += 1
        
        if file_count == 0:
            return jsonify({"error": "No files to download"}), 404
        
        memory_file.seek(0)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"DIXII_All_Documents_{timestamp}.zip"
        
        return send_file(
            memory_file,
            as_attachment=True,
            download_name=filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        logging.error(f"Error creating bulk download: {str(e)}")
        return jsonify({"error": "Failed to create download"}), 500

@app.route('/api/cleanup-uploads', methods=['POST'])
def cleanup_uploads():
    """Manually clean up old upload files"""
    try:
        data = request.get_json() or {}
        max_age_hours = data.get('max_age_hours', 1)  # Default to 1 hour
        
        # Count files before cleanup
        upload_folder = Config.UPLOAD_FOLDER
        files_before = len([f for f in os.listdir(upload_folder) if f not in ['.gitkeep', '.DS_Store']])
        
        cleanup_old_uploads(max_age_hours=max_age_hours)
        
        # Count files after cleanup
        files_after = len([f for f in os.listdir(upload_folder) if f not in ['.gitkeep', '.DS_Store']])
        files_removed = files_before - files_after
        
        return jsonify({
            "success": True, 
            "message": f"Upload cleanup completed - {files_removed} files removed (older than {max_age_hours} hours)",
            "files_removed": files_removed,
            "files_remaining": files_after
        })
        
    except Exception as e:
        logging.error(f"Error during manual upload cleanup: {str(e)}")
        return jsonify({"error": f"Failed to clean up uploads: {str(e)}"}), 500

@app.route('/api/cleanup-sessions', methods=['POST'])
def cleanup_sessions():
    """Manually clean up old processing sessions"""
    try:
        data = request.get_json() or {}
        max_age_hours = data.get('max_age_hours', 2)
        
        initial_count = len(processing_sessions)
        cleanup_old_sessions(max_age_hours=max_age_hours)
        final_count = len(processing_sessions)
        cleaned_count = initial_count - final_count
        
        return jsonify({
            "success": True, 
            "message": f"Session cleanup completed ({cleaned_count} sessions removed)",
            "sessions_removed": cleaned_count,
            "remaining_sessions": final_count
        })
        
    except Exception as e:
        logging.error(f"Error during manual session cleanup: {str(e)}")
        return jsonify({"error": f"Failed to clean up sessions: {str(e)}"}), 500

@app.route('/api/debug-sessions', methods=['GET'])
def debug_sessions():
    """Debug endpoint to check active sessions"""
    try:
        session_info = {}
        for session_id, session in processing_sessions.items():
            session_info[session_id] = {
                'status': session.get('status'),
                'current': session.get('current', 0),
                'total': session.get('total', 0),
                'current_file': session.get('current_file', ''),
                'processing_mode': session.get('processing_mode', 'unknown'),
                'results_count': len(session.get('results', []))
            }
        
        return jsonify({
            "success": True,
            "active_sessions": len(processing_sessions),
            "sessions": session_info
        })
        
    except Exception as e:
        logging.error(f"Error getting session debug info: {str(e)}")
        return jsonify({"error": f"Failed to get session info: {str(e)}"}), 500

@app.route('/api/debug-files', methods=['GET'])
def debug_files():
    """Debug endpoint to check processed files"""
    try:
        processed_path = Path(Config.PROCESSED_FOLDER)
        files_info = []
        
        if processed_path.exists():
            for root, dirs, files in os.walk(processed_path):
                for file in files:
                    file_path = Path(root) / file
                    relative_path = file_path.relative_to(processed_path)
                    files_info.append({
                        'filename': file,
                        'relative_path': str(relative_path).replace('\\', '/'),
                        'full_path': str(file_path),
                        'exists': file_path.exists(),
                        'size': file_path.stat().st_size if file_path.exists() else 0
                    })
        
        return jsonify({
            "success": True,
            "processed_folder": str(processed_path),
            "folder_exists": processed_path.exists(),
            "files_count": len(files_info),
            "files": files_info[:20]  # Limit to first 20 files for readability
        })
        
    except Exception as e:
        logging.error(f"Error getting files debug info: {str(e)}")
        return jsonify({"error": f"Failed to get files info: {str(e)}"}), 500

@app.route('/api/open-explorer', methods=['POST'])
def open_file_explorer():
    """Open local file explorer to show processed files folder"""
    try:
        import platform
        import subprocess
        
        processed_path = Path(Config.PROCESSED_FOLDER).absolute()
        
        # Ensure the folder exists
        processed_path.mkdir(exist_ok=True)
        
        system = platform.system()
        
        if system == "Windows":
            # Windows
            subprocess.run(f'explorer "{processed_path}"', shell=True)
        elif system == "Darwin":  # macOS
            # macOS
            subprocess.run(["open", str(processed_path)])
        elif system == "Linux":
            # Linux
            subprocess.run(["xdg-open", str(processed_path)])
        else:
            return jsonify({"error": f"Unsupported operating system: {system}"}), 400
        
        return jsonify({"success": True, "message": "File explorer opened", "path": str(processed_path)})
        
    except Exception as e:
        logging.error(f"Error opening file explorer: {str(e)}")
        return jsonify({"error": f"Failed to open file explorer: {str(e)}"}), 500

# Legacy compatibility routes
@app.route('/upload_legacy', methods=['POST'])
def upload_files_legacy():
    """Legacy upload endpoint for backward compatibility"""
    # Convert to enhanced format and process
    response = upload_files_enhanced()
    return response

@app.route('/batch_status/<session_id>')
def get_batch_status(session_id):
    """Get batch processing status for a session"""
    global processing_sessions, enhanced_processor
    
    if session_id not in processing_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = processing_sessions[session_id]
    
    # Get current batch processing status from processor
    batch_status = {}
    if enhanced_processor:
        try:
            batch_status = enhanced_processor.get_batch_processing_status()
        except Exception as e:
            logging.error(f"Error getting batch status: {e}")
    
    return jsonify({
        'session_status': session['status'],
        'processing_mode': session.get('processing_mode', 'unknown'),
        'batch_processing_status': batch_status,
        'current_file': session.get('current_file', ''),
        'progress': {
            'current': session.get('current', 0),
            'total': session.get('total', 0),
            'percentage': (session.get('current', 0) / session.get('total', 1)) * 100
        },
        'session_options': session.get('processing_options', {}),
        'processing_time': time.time() - session.get('processing_start_time', time.time()) if session.get('processing_start_time') else 0
    })

@app.route('/batch_processing_config', methods=['GET', 'POST'])
def batch_processing_config():
    """Configure batch processing settings"""
    global enhanced_processor
    
    if not enhanced_processor:
        return jsonify({'error': 'Enhanced processor not initialized'}), 500
    
    if request.method == 'GET':
        # Get current batch processing configuration
        status = enhanced_processor.get_batch_processing_status()
        return jsonify(status)
    
    elif request.method == 'POST':
        # Update batch processing configuration
        config = request.get_json()
        
        try:
            if config.get('enable_batch_processing'):
                enhanced_processor.enable_batch_processing()
            else:
                enhanced_processor.disable_batch_processing()
            
            return jsonify({
                'success': True,
                'message': 'Batch processing configuration updated',
                'current_status': enhanced_processor.get_batch_processing_status()
            })
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/batch_statistics')
def get_batch_statistics():
    """Get comprehensive batch processing statistics"""
    global enhanced_processor
    
    if not enhanced_processor:
        return jsonify({'error': 'Enhanced processor not initialized'}), 500
    
    try:
        stats = enhanced_processor.get_enhanced_processing_stats()
        batch_stats = stats.get('batch_processing', {})
        
        # Calculate performance summary
        summary = {
            'batch_processing_active': batch_stats.get('batch_processing_enabled', False),
            'total_documents_processed': batch_stats.get('total_documents_batched', 0) + batch_stats.get('total_individual_processed', 0),
            'batch_vs_individual_ratio': batch_stats.get('batch_vs_individual_ratio', 0.0),
            'strategy_effectiveness': batch_stats.get('batch_strategy_effectiveness', {}),
            'cost_optimization': {
                'average_cost_savings': batch_stats.get('average_cost_savings_rate', 0.0),
                'average_time_savings': batch_stats.get('average_time_savings_rate', 0.0)
            },
            'optimal_batch_sizes': batch_stats.get('optimal_batch_sizes', {})
        }
        
        return jsonify({
            'summary': summary,
            'detailed_stats': batch_stats,
            'system_health': stats.get('system_health', {})
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/manual_client_input', methods=['POST'])
def manual_client_input():
    """Handle manual client input and trigger learning"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        session_id = data.get('session_id')
        image_path = data.get('image_path')
        manual_name = data.get('manual_name')
        doc_type = data.get('doc_type')
        bbox_location = data.get('bbox_location')
        confidence = data.get('confidence', 1.0)
        
        if not session_id or not image_path or not manual_name:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Get the enhanced name detector
        global enhanced_processor
        if not enhanced_processor or not enhanced_processor.name_detector:
            return jsonify({'error': 'Name detector not available'}), 500
        
        # Learn from manual input
        enhanced_processor.name_detector.learn_from_manual_input(
            image_path=image_path,
            manual_name=manual_name,
            doc_type=doc_type,
            bbox_location=bbox_location,
            confidence=confidence
        )
        
        # Update session with manual input
        if session_id in processing_sessions:
            session = processing_sessions[session_id]
            if 'manual_inputs' not in session:
                session['manual_inputs'] = []
            
            session['manual_inputs'].append({
                'name': manual_name,
                'doc_type': doc_type,
                'timestamp': datetime.now().isoformat(),
                'confidence': confidence
            })
        
        return jsonify({
            'success': True,
            'message': f'Learned from manual input: {manual_name}',
            'session_id': session_id
        })
        
    except Exception as e:
        logging.error(f"Error in manual client input: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize enhanced processor on startup
    init_enhanced_processor()
    
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=8080) 