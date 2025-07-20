from flask import Flask, render_template, request, jsonify, send_from_directory, send_file, g
from flask_cors import CORS
import os
import uuid
import io
import zipfile
from werkzeug.utils import secure_filename
import threading
import time
import shutil
from pathlib import Path
from config import Config
from utils.file_processor import TaxDocumentProcessor
from database.supabase_client import init_database, test_database_connection, get_supabase
from database.models import (
    ClientDAO, ProcessingSessionDAO, DocumentResultDAO, StatisticsDAO,
    Client, ProcessingSession, DocumentResult
)
from auth import (
    require_auth, optional_auth, get_auth_service, get_current_user_id,
    get_current_user, AuthError, validate_user_file_access
)
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

# Enable CORS for frontend authentication
CORS(app, origins=['http://localhost:5000'], supports_credentials=True)

# Global variables for processing - keep as fallback for when DB is unavailable
processing_status = {}
processor = None
processor_initializing = False
database_available = False

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
    global database_available

    # Initialize database connection
    logger.info("Initializing database connection...")
    database_available = init_database()

    if database_available:
        logger.info("Database initialized successfully")
    else:
        logger.warning("Database initialization failed - continuing with in-memory storage")

    # Start background processor initialization
    import threading
    init_thread = threading.Thread(target=init_processor_background, daemon=True)
    init_thread.start()

    return True  # Always allow app to start

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

def process_documents_background(session_id, file_paths, user_id=None):
    """Background function to process documents"""
    global processing_status, processor, database_available

    if not processor:
        error_msg = 'Document processor not initialized'

        # Update both database and in-memory storage
        if database_available:
            ProcessingSessionDAO.update_session_status(session_id, 'error', error_msg)

        if session_id in processing_status:
            processing_status[session_id]['status'] = 'error'
            processing_status[session_id]['error'] = error_msg
        return

    try:
        total_files = len(file_paths)

        # Get manual client info if available
        manual_client_info = None
        processing_mode = 'auto'

        if session_id in processing_status:
            manual_client_info = processing_status[session_id].get('manual_client_info')
            processing_mode = processing_status[session_id].get('processing_mode', 'auto')

        # Create or get database session
        db_session = None
        if database_available and user_id:
            db_session = ProcessingSessionDAO.create_session(
                user_id=user_id,
                session_id=session_id,
                processing_mode=processing_mode,
                total_files=total_files,
                manual_client_info=manual_client_info
            )

        # Update in-memory storage
        if session_id in processing_status:
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

        # Create database document results if database is available
        document_results = []
        if database_available and db_session and user_id:
            for _, original_filename in file_paths:
                doc_result = DocumentResultDAO.create_document_result(
                    user_id=user_id,
                    session_uuid=session_id,  # Use the UUID string
                    original_filename=original_filename
                )
                document_results.append(doc_result)

        # Process each document
        for i, (file_path, original_filename) in enumerate(file_paths):
            try:
                # Update progress in memory
                if session_id in processing_status:
                    processing_status[session_id]['current'] = i + 1
                    processing_status[session_id]['current_file'] = original_filename
                    processing_status[session_id]['results'][i]['status'] = 'processing'

                # Update database document status
                if database_available and i < len(document_results) and document_results[i]:
                    DocumentResultDAO.update_document_result(
                        document_results[i].id,
                        status='processing'
                    )

                # Process the document with session_id parameter for database integration
                result = processor.process_document(
                    file_path,
                    original_filename,
                    manual_client_info
                )

                # Update in-memory result
                if session_id in processing_status:
                    processing_status[session_id]['results'][i] = result

                # Update database with processing result
                if database_available and i < len(document_results) and document_results[i]:
                    update_data = {
                        'status': result.get('status', 'completed'),
                        'new_filename': result.get('new_filename'),
                        'document_type': result.get('document_type'),
                        'tax_year': result.get('tax_year'),
                        'client_name': result.get('client_name'),
                        'client_folder': result.get('client_folder'),
                        'processed_path': result.get('processed_path'),
                        'confidence': result.get('confidence'),
                        'error_message': result.get('error'),
                        'file_size_bytes': result.get('file_size_bytes'),
                        'processing_time_seconds': result.get('processing_time_seconds')
                    }

                    # Link to client if we have client info
                    if result.get('client_name') and result.get('status') == 'completed' and user_id:
                        # Extract first and last name from client_name
                        name_parts = result['client_name'].split(' ', 1)
                        if len(name_parts) == 2:
                            first_name, last_name = name_parts
                            client = ClientDAO.find_or_create(user_id, first_name, last_name)
                            if client:
                                update_data['client_id'] = client.id

                    DocumentResultDAO.update_document_result(
                        document_results[i].id,
                        **update_data
                    )

                # Clean up uploaded file
                try:
                    os.remove(file_path)
                except:
                    pass

            except Exception as file_error:
                error_msg = str(file_error)
                logger.error(f"Error processing file {original_filename}: {error_msg}")

                # Update in-memory result
                if session_id in processing_status:
                    processing_status[session_id]['results'][i]['status'] = 'error'
                    processing_status[session_id]['results'][i]['error'] = error_msg

                # Update database result
                if database_available and i < len(document_results) and document_results[i]:
                    DocumentResultDAO.update_document_result(
                        document_results[i].id,
                        status='error',
                        error_message=error_msg
                    )

        # Count results for final status
        completed_count = 0
        error_count = 0

        if session_id in processing_status:
            for result in processing_status[session_id]['results']:
                if result['status'] == 'completed':
                    completed_count += 1
                elif result['status'] == 'error':
                    error_count += 1

            # Generate statistics
            stats = processor.get_processing_stats(processing_status[session_id]['results'])
            processing_status[session_id]['stats'] = stats
            processing_status[session_id]['status'] = 'completed'

        # Update database session status
        if database_available:
            ProcessingSessionDAO.update_session_status(
                session_id=session_id,
                status='completed',
                completed_files=completed_count,
                error_files=error_count
            )

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error in process_documents_background: {error_msg}")

        # Update in-memory status
        if session_id in processing_status:
            processing_status[session_id]['status'] = 'error'
            processing_status[session_id]['error'] = error_msg

        # Update database status
        if database_available:
            ProcessingSessionDAO.update_session_status(
                session_id=session_id,
                status='error',
                error_message=error_msg
            )

# =============================================
# AUTHENTICATION ENDPOINTS
# =============================================

@app.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    """User signup endpoint"""
    try:
        data = request.get_json()

        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password are required'}), 400

        email = data['email'].strip()
        password = data['password']

        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters long'}), 400

        # Optional user metadata
        user_metadata = {}
        if 'first_name' in data:
            user_metadata['first_name'] = data['first_name'].strip()
        if 'last_name' in data:
            user_metadata['last_name'] = data['last_name'].strip()

        auth_service = get_auth_service()
        result = auth_service.sign_up(email, password, user_metadata)

        return jsonify({
            'success': True,
            'user': result['user'],
            'session': result['session'],
            'message': 'Account created successfully! Please check your email to verify your account.'
        })

    except AuthError as e:
        return jsonify({'error': e.message}), e.status_code
    except Exception as e:
        logger.error(f"Signup error: {e}")
        return jsonify({'error': 'Account creation failed. Please try again.'}), 500

@app.route('/api/auth/signin', methods=['POST'])
def auth_signin():
    """User signin endpoint"""
    try:
        data = request.get_json()

        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password are required'}), 400

        email = data['email'].strip()
        password = data['password']

        auth_service = get_auth_service()
        result = auth_service.sign_in(email, password)

        return jsonify({
            'success': True,
            'user': result['user'],
            'session': result['session'],
            'message': 'Signed in successfully!'
        })

    except AuthError as e:
        return jsonify({'error': e.message}), e.status_code
    except Exception as e:
        logger.error(f"Signin error: {e}")
        return jsonify({'error': 'Sign in failed. Please check your credentials.'}), 500

@app.route('/api/auth/signout', methods=['POST'])
@require_auth
def auth_signout():
    """User signout endpoint"""
    try:
        auth_token = getattr(g, 'auth_token', None)

        if auth_token:
            auth_service = get_auth_service()
            auth_service.sign_out(auth_token)

        return jsonify({
            'success': True,
            'message': 'Signed out successfully!'
        })

    except Exception as e:
        logger.error(f"Signout error: {e}")
        return jsonify({'error': 'Sign out failed'}), 500

@app.route('/api/auth/user', methods=['GET'])
@require_auth
def auth_user():
    """Get current user information"""
    try:
        user = get_current_user()

        return jsonify({
            'success': True,
            'user': user
        })

    except Exception as e:
        logger.error(f"Get user error: {e}")
        return jsonify({'error': 'Failed to get user information'}), 500

@app.route('/api/auth/refresh', methods=['POST'])
def auth_refresh():
    """Refresh user session"""
    try:
        data = request.get_json()

        if not data or 'refresh_token' not in data:
            return jsonify({'error': 'Refresh token is required'}), 400

        refresh_token = data['refresh_token']

        auth_service = get_auth_service()
        result = auth_service.refresh_session(refresh_token)

        return jsonify({
            'success': True,
            'session': result,
            'message': 'Session refreshed successfully!'
        })

    except AuthError as e:
        return jsonify({'error': e.message}), e.status_code
    except Exception as e:
        logger.error(f"Refresh session error: {e}")
        return jsonify({'error': 'Session refresh failed'}), 500

# =============================================
# MAIN APPLICATION ROUTES
# =============================================

@app.route('/auth')
def auth_page():
    """Authentication page"""
    return render_template('auth.html')

@app.route('/test')
def test_page():
    """Test page without authentication"""
    return "<h1>Test Page - Flask is Working!</h1><p>If you see this, the Flask app is running correctly.</p><a href='/auth'>Go to Auth Page</a>"

@app.route('/')
@optional_auth
def index():
    """Main page with upload interface"""
    user = get_current_user()
    if not user:
        # Redirect unauthenticated users to auth page
        return render_template('auth.html')
    return render_template('index.html', user=user)

@app.route('/documents')
def documents_page():
    """Document management interface"""
    return render_template('documents.html')

@app.route('/clients')
def clients_page():
    """Client management interface"""
    return render_template('clients.html')

@app.route('/upload', methods=['POST'])
@require_auth
def upload_files():
    """Handle file upload and start processing"""
    global processing_status, processor, processor_initializing

    # Get authenticated user ID
    user_id = get_current_user_id()

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
        args=(session_id, file_paths, user_id)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'session_id': session_id})

@app.route('/status/<session_id>')
def get_status(session_id):
    """Get processing status for a session"""
    global processing_status, database_available

    # Try to get status from database first
    if database_available:
        try:
            db_session = ProcessingSessionDAO.get_by_session_id(session_id)
            if db_session:
                # Get document results for this session using session UUID
                documents = DocumentResultDAO.get_by_session_id(session_id)

                # Convert to the format expected by the frontend
                results = []
                current_file = ""
                current = 0

                for doc in documents:
                    result = {
                        'original_filename': doc.original_filename or '',
                        'status': doc.status or 'waiting',
                        'client_name': doc.client_name or None,
                        'document_type': doc.document_type or None,
                        'tax_year': doc.tax_year or None,
                        'new_filename': doc.new_filename or None,
                        'error': doc.error_message or None,
                        'confidence': float(doc.confidence) if doc.confidence else None,
                        'processed_path': doc.processed_path or None,
                        'client_folder': doc.client_folder or None
                    }
                    results.append(result)

                    if doc.status == 'processing':
                        current_file = doc.original_filename or ''
                        current = len([d for d in documents if d.status in ['completed', 'error']]) + 1

                # Generate stats from results if processor available
                stats = {}
                if processor and results:
                    try:
                        stats = processor.get_processing_stats(results)
                    except Exception as stats_error:
                        logger.error(f"Error generating stats: {stats_error}")
                        stats = {
                            'total_documents': len(results),
                            'completed': len([r for r in results if r['status'] == 'completed']),
                            'errors': len([r for r in results if r['status'] == 'error']),
                            'unique_clients': 0,
                            'success_rate': 0
                        }

                return jsonify({
                    'status': db_session.status or 'processing',
                    'total': db_session.total_files or 0,
                    'current': current,
                    'current_file': current_file,
                    'results': results,
                    'stats': stats,
                    'error': db_session.error_message,
                    'processing_mode': db_session.processing_mode or 'auto',
                    'manual_client_info': db_session.manual_client_info
                })
        except Exception as e:
            logger.error(f"Error getting status from database: {e}")
            # Fall through to in-memory lookup

    # Fallback to in-memory storage
    if session_id not in processing_status:
        return jsonify({'error': 'Session not found'}), 404

    return jsonify(processing_status[session_id])

@app.route('/results/<session_id>')
def get_results(session_id):
    """Get processing results for a session"""
    global processing_status, database_available

    # Try to get results from database first
    if database_available:
        try:
            db_session = ProcessingSessionDAO.get_by_session_id(session_id)
            if db_session:
                if db_session.status != 'completed':
                    return jsonify({'error': 'Processing not completed'}), 400

                # Get document results for this session using session UUID
                documents = DocumentResultDAO.get_by_session_id(session_id)

                # Convert to the format expected by the frontend
                results = []
                for doc in documents:
                    result = {
                        'original_filename': doc.original_filename,
                        'status': doc.status,
                        'client_name': doc.client_name,
                        'document_type': doc.document_type,
                        'tax_year': doc.tax_year,
                        'new_filename': doc.new_filename,
                        'error': doc.error_message,
                        'processed_path': doc.processed_path,
                        'client_folder': doc.client_folder,
                        'confidence': doc.confidence
                    }
                    results.append(result)

                # Generate stats from results
                if processor:
                    stats = processor.get_processing_stats(results)
                else:
                    stats = {}

                return jsonify({
                    'results': results,
                    'stats': stats
                })
        except Exception as e:
            logger.error(f"Error getting results from database: {e}")
            # Fall through to in-memory lookup

    # Fallback to in-memory storage
    if session_id not in processing_status:
        return jsonify({'error': 'Session not found'}), 404

    status = processing_status[session_id]
    if status['status'] != 'completed':
        return jsonify({'error': 'Processing not completed'}), 400

    return jsonify({
        'results': status['results'],
        'stats': status['stats']
    })

# New Database API Endpoints
@app.route('/api/clients')
@require_auth
def get_clients():
    """Get all clients with document counts"""
    global database_available

    user_id = get_current_user_id()
    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        clients = ClientDAO.get_all_with_stats(user_id)
        client_list = []

        for client in clients:
            client_data = {
                'id': client.id,
                'first_name': client.first_name,
                'last_name': client.last_name,
                'full_name': f"{client.first_name} {client.last_name}",
                'email': client.email,
                'phone': client.phone,
                'total_documents': client.total_documents,
                'completed_documents': client.completed_documents,
                'error_documents': client.error_documents,
                'unique_tax_years': client.unique_tax_years,
                'last_document_processed': client.last_document_processed.isoformat() if client.last_document_processed else None,
                'created_at': client.created_at.isoformat() if client.created_at else None
            }
            client_list.append(client_data)

        return jsonify({
            'success': True,
            'clients': client_list,
            'total_clients': len(client_list)
        })

    except Exception as e:
        logger.error(f"Error getting clients: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<client_id>/documents')
def get_client_documents(client_id):
    """Get documents for specific client"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        limit = request.args.get('limit', type=int)
        documents = DocumentResultDAO.get_by_client_id(client_id, limit)

        document_list = []
        for doc in documents:
            doc_data = {
                'id': doc.id,
                'original_filename': doc.original_filename,
                'new_filename': doc.new_filename,
                'document_type': doc.document_type,
                'tax_year': doc.tax_year,
                'status': doc.status,
                'confidence': doc.confidence,
                'processed_path': doc.processed_path,
                'created_at': doc.created_at.isoformat() if doc.created_at else None,
                'error_message': doc.error_message
            }
            document_list.append(doc_data)

        return jsonify({
            'success': True,
            'documents': document_list,
            'total_documents': len(document_list)
        })

    except Exception as e:
        logger.error(f"Error getting client documents: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/statistics')
def get_statistics():
    """Get processing statistics (last 30 days by default)"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        days = request.args.get('days', 30, type=int)
        stats = StatisticsDAO.get_processing_statistics(days)

        # Also get document type summary
        doc_types = StatisticsDAO.get_document_type_summary()

        return jsonify({
            'success': True,
            'statistics': stats,
            'document_types': doc_types
        })

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/recent-sessions')
def get_recent_sessions():
    """Get recent processing sessions"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        limit = request.args.get('limit', 20, type=int)
        sessions = ProcessingSessionDAO.get_recent_sessions(limit)

        session_list = []
        for session in sessions:
            session_data = {
                'id': session.id,
                'session_id': session.session_id,
                'status': session.status,
                'processing_mode': session.processing_mode,
                'total_files': session.total_files,
                'completed_files': session.completed_files,
                'error_files': session.error_files,
                'error_message': session.error_message,
                'started_at': session.started_at.isoformat() if session.started_at else None,
                'completed_at': session.completed_at.isoformat() if session.completed_at else None,
                'created_at': session.created_at.isoformat() if session.created_at else None
            }
            session_list.append(session_data)

        return jsonify({
            'success': True,
            'sessions': session_list,
            'total_sessions': len(session_list)
        })

    except Exception as e:
        logger.error(f"Error getting recent sessions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/search')
def search_documents():
    """Search documents with filters (client, doc type, tax year)"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        client_name = request.args.get('client_name')
        document_type = request.args.get('document_type')
        tax_year = request.args.get('tax_year', type=int)
        limit = request.args.get('limit', 100, type=int)

        documents = DocumentResultDAO.search_documents(
            client_name=client_name,
            document_type=document_type,
            tax_year=tax_year,
            limit=limit
        )

        document_list = []
        for doc in documents:
            doc_data = {
                'id': doc.id,
                'original_filename': doc.original_filename,
                'new_filename': doc.new_filename,
                'document_type': doc.document_type,
                'tax_year': doc.tax_year,
                'client_name': doc.client_name,
                'status': doc.status,
                'confidence': doc.confidence,
                'processed_path': doc.processed_path,
                'created_at': doc.created_at.isoformat() if doc.created_at else None,
                'error_message': doc.error_message
            }
            document_list.append(doc_data)

        return jsonify({
            'success': True,
            'documents': document_list,
            'total_documents': len(document_list),
            'filters': {
                'client_name': client_name,
                'document_type': document_type,
                'tax_year': tax_year
            }
        })

    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/session/<session_id>/documents')
def get_session_documents(session_id):
    """Get all documents from a session"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        # Get the processing session first
        db_session = ProcessingSessionDAO.get_by_session_id(session_id)
        if not db_session:
            return jsonify({'error': 'Session not found'}), 404

        # Get documents for this session using session UUID
        documents = DocumentResultDAO.get_by_session_id(session_id)

        document_list = []
        for doc in documents:
            doc_data = {
                'id': doc.id,
                'original_filename': doc.original_filename,
                'new_filename': doc.new_filename,
                'document_type': doc.document_type,
                'tax_year': doc.tax_year,
                'client_name': doc.client_name,
                'status': doc.status,
                'confidence': doc.confidence,
                'processed_path': doc.processed_path,
                'created_at': doc.created_at.isoformat() if doc.created_at else None,
                'error_message': doc.error_message
            }
            document_list.append(doc_data)

        return jsonify({
            'success': True,
            'session': {
                'id': db_session.id,
                'session_id': db_session.session_id,
                'status': db_session.status,
                'processing_mode': db_session.processing_mode,
                'total_files': db_session.total_files,
                'completed_files': db_session.completed_files,
                'error_files': db_session.error_files
            },
            'documents': document_list,
            'total_documents': len(document_list)
        })

    except Exception as e:
        logger.error(f"Error getting session documents: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database-status')
def get_database_status():
    """Check database connection health"""
    try:
        status = test_database_connection()
        return jsonify(status)
    except Exception as e:
        return jsonify({
            'connected': False,
            'status': 'error',
            'message': f'Database status check failed: {str(e)}'
        }), 500

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
            print(f"📋 Checking result {i}: {result.get('original_filename')}")
            print(f"   Status: {result['status']}")
            print(f"   Processed path: {result.get('processed_path')}")
            print(f"   File exists: {os.path.exists(result.get('processed_path', '')) if result.get('processed_path') else 'No path'}")

            if (result['status'] == 'completed' and
                result.get('processed_path') and
                os.path.exists(result['processed_path'])):

                # Check if file is PDF or image
                file_ext = os.path.splitext(result['processed_path'])[1].lower()
                print(f"   File extension: {file_ext}")

                if file_ext in ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                    # Get relative path from processed folder for the preview endpoint
                    rel_path = os.path.relpath(result['processed_path'], Config.PROCESSED_FOLDER)

                    # Verify the relative path works
                    test_full_path = os.path.join(Config.PROCESSED_FOLDER, rel_path)
                    if not os.path.exists(test_full_path):
                        print(f"Warning: Relative path verification failed for {result['original_filename']}")
                        continue

                    print(f"   ✅ Adding to preview files: {rel_path}")
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
                else:
                    print(f"   ❌ File extension {file_ext} not supported for preview")
            else:
                print(f"   ❌ File not eligible: status={result['status']}, has_path={bool(result.get('processed_path'))}")

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

# Document Management System Endpoints
@app.route('/api/documents')
def get_all_documents():
    """Get all documents with pagination and filters for document management"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)  # Max 100 per page
        client_id = request.args.get('client_id', type=int)
        client_name = request.args.get('client_name')
        document_type = request.args.get('document_type')
        tax_year = request.args.get('tax_year', type=int)
        status = request.args.get('status')
        sort_by = request.args.get('sort_by', 'created_at')  # created_at, client_name, document_type, tax_year
        sort_order = request.args.get('sort_order', 'desc')  # asc, desc

        # Validate sort parameters
        valid_sort_fields = ['created_at', 'client_name', 'document_type', 'tax_year', 'original_filename']
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'

        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'

        supabase = get_supabase()

        # Build query
        query = supabase.table('document_results').select('*')

        # Apply filters
        if client_id:
            query = query.eq('client_id', client_id)
        if client_name:
            query = query.ilike('client_name', f'%{client_name}%')
        if document_type:
            query = query.ilike('document_type', f'%{document_type}%')
        if tax_year:
            query = query.eq('tax_year', tax_year)
        if status:
            query = query.eq('status', status)

        # Apply sorting
        query = query.order(sort_by, desc=(sort_order == 'desc'))

        # Apply pagination
        offset = (page - 1) * per_page
        query = query.range(offset, offset + per_page - 1)

        result = query.execute()

        # Get total count for pagination
        count_query = supabase.table('document_results').select('id')
        if client_id:
            count_query = count_query.eq('client_id', client_id)
        if client_name:
            count_query = count_query.ilike('client_name', f'%{client_name}%')
        if document_type:
            count_query = count_query.ilike('document_type', f'%{document_type}%')
        if tax_year:
            count_query = count_query.eq('tax_year', tax_year)
        if status:
            count_query = count_query.eq('status', status)

        count_result = count_query.execute()
        total_count = len(count_result.data)

        # Format documents
        documents = []
        for doc_data in result.data:
            doc = {
                'id': doc_data['id'],
                'original_filename': doc_data['original_filename'],
                'new_filename': doc_data.get('new_filename'),
                'document_type': doc_data.get('document_type'),
                'tax_year': doc_data.get('tax_year'),
                'client_name': doc_data.get('client_name'),
                'client_id': doc_data.get('client_id'),
                'status': doc_data['status'],
                'confidence': doc_data.get('confidence'),
                'processed_path': doc_data.get('processed_path'),
                'file_size_bytes': doc_data.get('file_size_bytes'),
                'created_at': doc_data['created_at'],
                'error_message': doc_data.get('error_message'),

                # Add file availability check
                'file_available': False,
                'preview_url': None,
                'download_url': None
            }

            # Check if file exists and add URLs
            if doc_data.get('processed_path') and os.path.exists(doc_data['processed_path']):
                doc['file_available'] = True
                rel_path = os.path.relpath(doc_data['processed_path'], Config.PROCESSED_FOLDER)
                doc['preview_url'] = f"/preview/{rel_path}"
                doc['download_url'] = f"/download/{rel_path}"

            documents.append(doc)

        # Calculate pagination info
        total_pages = (total_count + per_page - 1) // per_page

        return jsonify({
            'success': True,
            'documents': documents,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'filters': {
                'client_id': client_id,
                'client_name': client_name,
                'document_type': document_type,
                'tax_year': tax_year,
                'status': status,
                'sort_by': sort_by,
                'sort_order': sort_order
            }
        })

    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<int:document_id>')
def get_document_details(document_id):
    """Get detailed information about a specific document"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        # Get document with client info
        result = supabase.table('document_results')\
            .select('*, clients(*)')\
            .eq('id', document_id)\
            .execute()

        if not result.data:
            return jsonify({'error': 'Document not found'}), 404

        doc_data = result.data[0]
        client_data = doc_data.get('clients')

        document = {
            'id': doc_data['id'],
            'original_filename': doc_data['original_filename'],
            'new_filename': doc_data.get('new_filename'),
            'document_type': doc_data.get('document_type'),
            'tax_year': doc_data.get('tax_year'),
            'client_name': doc_data.get('client_name'),
            'client_folder': doc_data.get('client_folder'),
            'status': doc_data['status'],
            'confidence': doc_data.get('confidence'),
            'processed_path': doc_data.get('processed_path'),
            'file_size_bytes': doc_data.get('file_size_bytes'),
            'processing_time_seconds': doc_data.get('processing_time_seconds'),
            'created_at': doc_data['created_at'],
            'updated_at': doc_data['updated_at'],
            'error_message': doc_data.get('error_message'),

            # Client details
            'client': None,

            # File info
            'file_available': False,
            'file_size_formatted': None,
            'preview_url': None,
            'download_url': None
        }

        # Add client info if available
        if client_data:
            document['client'] = {
                'id': client_data['id'],
                'first_name': client_data['first_name'],
                'last_name': client_data['last_name'],
                'name': client_data.get('name'),
                'email': client_data.get('email'),
                'phone': client_data.get('phone')
            }

        # Check file availability and add file info
        if doc_data.get('processed_path') and os.path.exists(doc_data['processed_path']):
            document['file_available'] = True
            rel_path = os.path.relpath(doc_data['processed_path'], Config.PROCESSED_FOLDER)
            document['preview_url'] = f"/preview/{rel_path}"
            document['download_url'] = f"/download/{rel_path}"

            # Format file size
            if doc_data.get('file_size_bytes'):
                size_bytes = doc_data['file_size_bytes']
                if size_bytes < 1024:
                    document['file_size_formatted'] = f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    document['file_size_formatted'] = f"{size_bytes / 1024:.1f} KB"
                else:
                    document['file_size_formatted'] = f"{size_bytes / (1024 * 1024):.1f} MB"

        return jsonify({
            'success': True,
            'document': document
        })

    except Exception as e:
        logger.error(f"Error getting document details: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/summary')
def get_documents_summary():
    """Get summary statistics for document management dashboard"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        # Get overall stats
        total_result = supabase.table('document_results').select('id').execute()
        total_documents = len(total_result.data)

        completed_result = supabase.table('document_results').select('id').eq('status', 'completed').execute()
        completed_documents = len(completed_result.data)

        error_result = supabase.table('document_results').select('id').eq('status', 'error').execute()
        error_documents = len(error_result.data)

        # Get unique clients count
        clients_result = supabase.table('document_results').select('client_id').execute()
        unique_clients = len(set(item['client_id'] for item in clients_result.data if item['client_id']))

        # Get document types breakdown
        doc_types_result = supabase.table('document_type_statistics').select('*').limit(10).execute()

        # Get recent documents
        recent_result = supabase.table('document_results')\
            .select('original_filename, client_name, document_type, created_at')\
            .order('created_at', desc=True)\
            .limit(5)\
            .execute()

        # Get tax years distribution
        tax_years_result = supabase.table('tax_year_statistics').select('*').limit(10).execute()

        return jsonify({
            'success': True,
            'summary': {
                'total_documents': total_documents,
                'completed_documents': completed_documents,
                'error_documents': error_documents,
                'success_rate': (completed_documents / total_documents * 100) if total_documents > 0 else 0,
                'unique_clients': unique_clients
            },
            'document_types': doc_types_result.data,
            'tax_years': tax_years_result.data,
            'recent_documents': recent_result.data
        })

    except Exception as e:
        logger.error(f"Error getting documents summary: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/by-client/<int:client_id>')
def get_client_document_browser(client_id):
    """Get documents for a specific client organized for browsing"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        # Get client info
        client_result = supabase.table('clients').select('*').eq('id', client_id).execute()
        if not client_result.data:
            return jsonify({'error': 'Client not found'}), 404

        client = client_result.data[0]

        # Get documents for this client
        docs_result = supabase.table('document_results')\
            .select('*')\
            .eq('client_id', client_id)\
            .order('created_at', desc=True)\
            .execute()

        # Organize documents by tax year and type
        documents_by_year = {}
        documents_by_type = {}

        for doc_data in docs_result.data:
            doc = {
                'id': doc_data['id'],
                'original_filename': doc_data['original_filename'],
                'new_filename': doc_data.get('new_filename'),
                'document_type': doc_data.get('document_type') or 'Unknown',
                'tax_year': doc_data.get('tax_year'),
                'status': doc_data['status'],
                'confidence': doc_data.get('confidence'),
                'created_at': doc_data['created_at'],
                'file_available': False,
                'preview_url': None,
                'download_url': None
            }

            # Check file availability
            if doc_data.get('processed_path') and os.path.exists(doc_data['processed_path']):
                doc['file_available'] = True
                rel_path = os.path.relpath(doc_data['processed_path'], Config.PROCESSED_FOLDER)
                doc['preview_url'] = f"/preview/{rel_path}"
                doc['download_url'] = f"/download/{rel_path}"

            # Organize by tax year
            year = doc['tax_year'] or 'Unknown Year'
            if year not in documents_by_year:
                documents_by_year[year] = []
            documents_by_year[year].append(doc)

            # Organize by document type
            doc_type = doc['document_type']
            if doc_type not in documents_by_type:
                documents_by_type[doc_type] = []
            documents_by_type[doc_type].append(doc)

        return jsonify({
            'success': True,
            'client': {
                'id': client['id'],
                'first_name': client['first_name'],
                'last_name': client['last_name'],
                'name': client.get('name'),
                'email': client.get('email'),
                'phone': client.get('phone')
            },
            'total_documents': len(docs_result.data),
            'documents_by_year': documents_by_year,
            'documents_by_type': documents_by_type,
            'all_documents': [doc for docs in documents_by_year.values() for doc in docs]
        })

    except Exception as e:
        logger.error(f"Error getting client documents: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<int:document_id>/move', methods=['POST'])
def move_document(document_id):
    """Move a document to a different client"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        data = request.json
        new_client_id = data.get('client_id')

        if not new_client_id:
            return jsonify({'error': 'client_id is required'}), 400

        supabase = get_supabase()

        # Verify new client exists
        client_result = supabase.table('clients').select('*').eq('id', new_client_id).execute()
        if not client_result.data:
            return jsonify({'error': 'Target client not found'}), 404

        new_client = client_result.data[0]

        # Update document
        result = supabase.table('document_results')\
            .update({
                'client_id': new_client_id,
                'client_name': new_client.get('name') or f"{new_client['first_name']} {new_client['last_name']}"
            })\
            .eq('id', document_id)\
            .execute()

        if not result.data:
            return jsonify({'error': 'Document not found'}), 404

        return jsonify({
            'success': True,
            'message': f"Document moved to {new_client.get('name') or f'{new_client['first_name']} {new_client['last_name']}'}"
        })

    except Exception as e:
        logger.error(f"Error moving document: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/bulk-delete', methods=['POST'])
def bulk_delete_documents():
    """Delete multiple documents"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        data = request.json
        document_ids = data.get('document_ids', [])

        if not document_ids:
            return jsonify({'error': 'document_ids array is required'}), 400

        supabase = get_supabase()

        # Get documents to delete (to clean up files)
        docs_result = supabase.table('document_results')\
            .select('processed_path')\
            .in_('id', document_ids)\
            .execute()

        # Delete files from filesystem
        deleted_files = 0
        for doc in docs_result.data:
            if doc.get('processed_path') and os.path.exists(doc['processed_path']):
                try:
                    os.remove(doc['processed_path'])
                    deleted_files += 1
                except Exception as e:
                    logger.warning(f"Could not delete file {doc['processed_path']}: {e}")

        # Delete from database
        result = supabase.table('document_results')\
            .delete()\
            .in_('id', document_ids)\
            .execute()

        deleted_count = len(result.data) if result.data else 0

        return jsonify({
            'success': True,
            'deleted_documents': deleted_count,
            'deleted_files': deleted_files,
            'message': f"Deleted {deleted_count} documents and {deleted_files} files"
        })

    except Exception as e:
        logger.error(f"Error bulk deleting documents: {e}")
        return jsonify({'error': str(e)}), 500

# =============================================================================
# ENTERPRISE API ENDPOINTS - Enhanced functionality for document management
# =============================================================================

@app.route('/api/documents/advanced-search', methods=['POST'])
def advanced_document_search():
    """Advanced multi-field document search with filters, sorting, pagination"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        data = request.json
        search_query = data.get('searchQuery', '')
        client_id = data.get('clientId')
        document_type = data.get('documentType')
        tax_year = data.get('taxYear')
        status = data.get('status')
        date_from = data.get('dateFrom')
        date_to = data.get('dateTo')
        has_annotations = data.get('hasAnnotations')
        confidence_min = data.get('confidenceMin')
        sort_by = data.get('sortBy', 'created_at')
        sort_order = data.get('sortOrder', 'desc')
        page = int(data.get('page', 1))
        page_size = int(data.get('pageSize', 20))

        supabase = get_supabase()

        # Convert parameters for the database function
        client_id_param = int(client_id) if client_id and client_id != '' else None
        tax_year_param = int(tax_year) if tax_year and tax_year != '' else None
        confidence_min_param = float(confidence_min) if confidence_min and confidence_min != '' else None
        date_from_param = date_from if date_from and date_from != '' else None
        date_to_param = date_to if date_to and date_to != '' else None
        has_annotations_param = has_annotations if has_annotations and has_annotations != '' else None
        status_param = status if status and status != '' else None
        document_type_param = document_type if document_type and document_type != '' else None

        # Calculate offset
        offset = (page - 1) * page_size

        # Call the enhanced search function
        result = supabase.rpc('advanced_document_search', {
            'search_query': search_query,
            'client_id_filter': client_id_param,
            'document_type_filter': document_type_param,
            'tax_year_filter': tax_year_param,
            'status_filter': status_param,
            'date_from': date_from_param,
            'date_to': date_to_param,
            'has_annotations': has_annotations_param,
            'confidence_min': confidence_min_param,
            'sort_by': sort_by,
            'sort_order': sort_order.upper(),
            'limit_count': page_size,
            'offset_count': offset
        }).execute()

        documents = []
        for doc_data in result.data:
            doc = {
                'id': doc_data['id'],
                'session_id': doc_data['session_id'],
                'client_id': doc_data['client_id'],
                'original_filename': doc_data['original_filename'],
                'new_filename': doc_data.get('new_filename'),
                'document_type': doc_data.get('document_type'),
                'tax_year': doc_data.get('tax_year'),
                'client_name': doc_data.get('client_name'),
                'status': doc_data['status'],
                'confidence': doc_data.get('confidence'),
                'file_size_bytes': doc_data.get('file_size_bytes'),
                'annotation_count': doc_data.get('annotation_count', 0),
                'created_at': doc_data['created_at'],
                'client_full_name': doc_data.get('client_full_name'),
                'business_type': doc_data.get('business_type')
            }
            documents.append(doc)

        # Get total count for pagination (simplified approach)
        total_items = len(documents) if len(documents) < page_size else (page * page_size) + 1
        total_pages = (total_items + page_size - 1) // page_size

        pagination = {
            'currentPage': page,
            'pageSize': page_size,
            'totalPages': total_pages,
            'totalItems': total_items
        }

        return jsonify({
            'success': True,
            'data': documents,
            'pagination': pagination
        })

    except Exception as e:
        logger.error(f"Error in advanced document search: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<int:doc_id>/annotations', methods=['GET', 'POST'])
def document_annotations(doc_id):
    """CRUD operations for document annotations"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        if request.method == 'GET':
            # Get all annotations for a document
            result = supabase.table('document_annotations')\
                .select('*')\
                .eq('document_id', doc_id)\
                .order('created_at', desc=True)\
                .execute()

            return jsonify({
                'success': True,
                'data': result.data
            })

        elif request.method == 'POST':
            # Create new annotation
            data = request.json
            annotation_data = {
                'document_id': doc_id,
                'annotation_type': data.get('annotation_type', 'note'),
                'content': data.get('content', ''),
                'position_data': data.get('position_data'),
                'created_by': data.get('created_by', 'System')
            }

            result = supabase.table('document_annotations')\
                .insert(annotation_data)\
                .execute()

            return jsonify({
                'success': True,
                'data': result.data[0] if result.data else None
            })

    except Exception as e:
        logger.error(f"Error handling document annotations: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<int:doc_id>/annotations/<int:annotation_id>', methods=['DELETE'])
def delete_annotation(doc_id, annotation_id):
    """Delete a specific annotation"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        result = supabase.table('document_annotations')\
            .delete()\
            .eq('id', annotation_id)\
            .eq('document_id', doc_id)\
            .execute()

        return jsonify({
            'success': True,
            'message': 'Annotation deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting annotation: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/dashboard')
def clients_dashboard_data():
    """Get comprehensive client data for dashboard"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        # Use the client dashboard view
        result = supabase.table('client_dashboard_data')\
            .select('*')\
            .order('total_documents', desc=True)\
            .execute()

        return jsonify({
            'success': True,
            'data': result.data
        })

    except Exception as e:
        logger.error(f"Error getting client dashboard data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:client_id>/dashboard')
def client_dashboard_data(client_id):
    """Get comprehensive client data for individual client dashboard"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        # Get client with profile data
        client_result = supabase.table('client_dashboard_data')\
            .select('*')\
            .eq('id', client_id)\
            .execute()

        if not client_result.data:
            return jsonify({'error': 'Client not found'}), 404

        client_data = client_result.data[0]

        # Get recent documents
        recent_docs_result = supabase.table('document_results')\
            .select('*')\
            .eq('client_id', client_id)\
            .order('created_at', desc=True)\
            .limit(10)\
            .execute()

        # Get document summary by type
        doc_types_result = supabase.table('document_results')\
            .select('document_type')\
            .eq('client_id', client_id)\
            .execute()

        doc_type_counts = {}
        for doc in doc_types_result.data:
            doc_type = doc.get('document_type') or 'Unknown'
            doc_type_counts[doc_type] = doc_type_counts.get(doc_type, 0) + 1

        client_data['recent_documents'] = recent_docs_result.data
        client_data['document_type_summary'] = doc_type_counts

        return jsonify({
            'success': True,
            'data': client_data
        })

    except Exception as e:
        logger.error(f"Error getting client dashboard data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:client_id>/full')
def get_client_full_data(client_id):
    """Get full client data including profile"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        # Get client with profile
        client_result = supabase.table('clients')\
            .select('*, client_profiles(*)')\
            .eq('id', client_id)\
            .execute()

        if not client_result.data:
            return jsonify({'error': 'Client not found'}), 404

        client_data = client_result.data[0]

        # Flatten profile data
        if client_data.get('client_profiles'):
            profile = client_data['client_profiles'][0] if client_data['client_profiles'] else {}
            client_data.update({
                'business_type': profile.get('business_type'),
                'tax_id': profile.get('tax_id'),
                'preferred_contact': profile.get('preferred_contact'),
                'filing_frequency': profile.get('filing_frequency'),
                'portal_access': profile.get('portal_access'),
                'compliance_status': profile.get('compliance_status'),
                'profile_notes': profile.get('notes')
            })
            del client_data['client_profiles']

        return jsonify({
            'success': True,
            'data': client_data
        })

    except Exception as e:
        logger.error(f"Error getting full client data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:client_id>/communications', methods=['GET', 'POST'])
def client_communications(client_id):
    """Handle client communications"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        if request.method == 'GET':
            # Get all communications for client
            result = supabase.table('client_communications')\
                .select('*')\
                .eq('client_id', client_id)\
                .order('communication_date', desc=True)\
                .execute()

            return jsonify({
                'success': True,
                'data': result.data
            })

        elif request.method == 'POST':
            # Create new communication
            data = request.json
            comm_data = {
                'client_id': client_id,
                'communication_type': data.get('communication_type'),
                'subject': data.get('subject'),
                'content': data.get('content'),
                'communication_date': data.get('communication_date'),
                'created_by': data.get('created_by', 'System')
            }

            result = supabase.table('client_communications')\
                .insert(comm_data)\
                .execute()

            return jsonify({
                'success': True,
                'data': result.data[0] if result.data else None
            })

    except Exception as e:
        logger.error(f"Error handling client communications: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<int:doc_id>/related')
def get_related_documents(doc_id):
    """Find related documents (same client, year, type)"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()
        filter_type = request.args.get('filter', 'all')

        # Get the base document
        base_doc_result = supabase.table('document_results')\
            .select('*')\
            .eq('id', doc_id)\
            .execute()

        if not base_doc_result.data:
            return jsonify({'error': 'Document not found'}), 404

        base_doc = base_doc_result.data[0]

        # Build query based on filter type
        query = supabase.table('document_results').select('*')

        if filter_type == 'client':
            query = query.eq('client_id', base_doc['client_id'])
        elif filter_type == 'year':
            if base_doc.get('tax_year'):
                query = query.eq('tax_year', base_doc['tax_year'])
        elif filter_type == 'type':
            if base_doc.get('document_type'):
                query = query.eq('document_type', base_doc['document_type'])
        else:  # 'all' - related by any criteria
            query = query.or_(f"client_id.eq.{base_doc['client_id']}")
            if base_doc.get('tax_year'):
                query = query.or_(f"tax_year.eq.{base_doc['tax_year']}")
            if base_doc.get('document_type'):
                query = query.or_(f"document_type.eq.{base_doc['document_type']}")

        # Exclude the current document and execute
        result = query.neq('id', doc_id)\
            .order('created_at', desc=True)\
            .limit(20)\
            .execute()

        return jsonify({
            'success': True,
            'data': result.data
        })

    except Exception as e:
        logger.error(f"Error getting related documents: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<int:doc_id>/full')
def get_document_full_data(doc_id):
    """Get complete document data including metadata"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        # Get document with client info
        doc_result = supabase.table('document_results')\
            .select('*, clients(name, email, phone)')\
            .eq('id', doc_id)\
            .execute()

        if not doc_result.data:
            return jsonify({'error': 'Document not found'}), 404

        doc_data = doc_result.data[0]

        # Format client info
        if doc_data.get('clients'):
            doc_data['client_info'] = doc_data['clients']
            del doc_data['clients']

        return jsonify({
            'success': True,
            'data': doc_data
        })

    except Exception as e:
        logger.error(f"Error getting full document data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/types')
def get_document_types():
    """Get list of available document types"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        result = supabase.table('document_results')\
            .select('document_type')\
            .execute()

        # Get unique document types
        types = set()
        for doc in result.data:
            if doc.get('document_type'):
                types.add(doc['document_type'])

        return jsonify(sorted(list(types)))

    except Exception as e:
        logger.error(f"Error getting document types: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/years')
def get_tax_years():
    """Get list of available tax years"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        result = supabase.table('document_results')\
            .select('tax_year')\
            .execute()

        # Get unique tax years
        years = set()
        for doc in result.data:
            if doc.get('tax_year'):
                years.add(doc['tax_year'])

        return jsonify(sorted(list(years), reverse=True))

    except Exception as e:
        logger.error(f"Error getting tax years: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/saved-searches', methods=['GET', 'POST'])
def saved_searches():
    """Handle saved search queries"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        if request.method == 'GET':
            # Get all saved searches
            result = supabase.table('saved_searches')\
                .select('*')\
                .order('created_at', desc=True)\
                .execute()

            return jsonify(result.data)

        elif request.method == 'POST':
            # Create new saved search
            data = request.json
            search_data = {
                'search_name': data.get('search_name'),
                'search_criteria': data.get('search_criteria'),
                'user_id': data.get('user_id', 'default'),
                'is_shared': data.get('is_shared', False)
            }

            result = supabase.table('saved_searches')\
                .insert(search_data)\
                .execute()

            return jsonify({
                'success': True,
                'data': result.data[0] if result.data else None
            })

    except Exception as e:
        logger.error(f"Error handling saved searches: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/saved-searches/<int:search_id>', methods=['DELETE'])
def delete_saved_search(search_id):
    """Delete a saved search"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        result = supabase.table('saved_searches')\
            .delete()\
            .eq('id', search_id)\
            .execute()

        return jsonify({
            'success': True,
            'message': 'Saved search deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting saved search: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/overview')
def analytics_overview():
    """High-level analytics for admin dashboard"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        # Get processing statistics
        processing_stats = supabase.table('processing_statistics')\
            .select('*')\
            .order('processing_date', desc=True)\
            .limit(30)\
            .execute()

        # Get document type analytics
        doc_type_stats = supabase.table('document_type_analytics')\
            .select('*')\
            .limit(10)\
            .execute()

        # Get recent activity
        recent_activity = supabase.table('recent_activity_enhanced')\
            .select('*')\
            .limit(20)\
            .execute()

        # Calculate totals
        total_clients = supabase.table('clients').select('id', count='exact').execute()
        total_documents = supabase.table('document_results').select('id', count='exact').execute()

        return jsonify({
            'success': True,
            'data': {
                'processing_statistics': processing_stats.data,
                'document_type_analytics': doc_type_stats.data,
                'recent_activity': recent_activity.data,
                'totals': {
                    'clients': total_clients.count,
                    'documents': total_documents.count
                }
            }
        })

    except Exception as e:
        logger.error(f"Error getting analytics overview: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/download-multiple', methods=['POST'])
def download_multiple_documents():
    """Download multiple documents as a ZIP file"""
    import zipfile
    import io

    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        data = request.json
        document_ids = data.get('documentIds', [])

        if not document_ids:
            return jsonify({'error': 'No documents specified'}), 400

        supabase = get_supabase()

        # Get document paths
        docs_result = supabase.table('document_results')\
            .select('original_filename, processed_path')\
            .in_('id', document_ids)\
            .execute()

        # Create ZIP file in memory
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for doc in docs_result.data:
                file_path = doc.get('processed_path')
                if file_path and os.path.exists(file_path):
                    zip_file.write(file_path, doc['original_filename'])

        zip_buffer.seek(0)

        return send_file(
            io.BytesIO(zip_buffer.read()),
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'documents_{len(document_ids)}_files.zip'
        )

    except Exception as e:
        logger.error(f"Error creating document archive: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/delete-multiple', methods=['POST'])
def delete_multiple_documents():
    """Delete multiple documents"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        data = request.json
        document_ids = data.get('documentIds', [])

        if not document_ids:
            return jsonify({'error': 'No documents specified'}), 400

        supabase = get_supabase()

        # Get document paths for file cleanup
        docs_result = supabase.table('document_results')\
            .select('processed_path')\
            .in_('id', document_ids)\
            .execute()

        # Delete files from filesystem
        deleted_files = 0
        for doc in docs_result.data:
            file_path = doc.get('processed_path')
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    deleted_files += 1
                except Exception as e:
                    logger.warning(f"Could not delete file {file_path}: {e}")

        # Delete from database
        result = supabase.table('document_results')\
            .delete()\
            .in_('id', document_ids)\
            .execute()

        return jsonify({
            'success': True,
            'deleted_count': len(result.data) if result.data else 0,
            'deleted_files': deleted_files
        })

    except Exception as e:
        logger.error(f"Error deleting multiple documents: {e}")
        return jsonify({'error': str(e)}), 500

# Add client CRUD operations
@app.route('/api/clients', methods=['GET', 'POST'])
def clients_api():
    """Handle client operations"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        if request.method == 'GET':
            # Get all clients
            result = supabase.table('clients')\
                .select('*')\
                .order('name')\
                .execute()

            return jsonify(result.data)

        elif request.method == 'POST':
            # Create new client
            data = request.json

            # Create client record
            client_data = {
                'first_name': data.get('first_name'),
                'last_name': data.get('last_name'),
                'email': data.get('email'),
                'phone': data.get('phone')
            }

            client_result = supabase.table('clients')\
                .insert(client_data)\
                .execute()

            if client_result.data:
                client_id = client_result.data[0]['id']

                # Create client profile
                profile_data = {
                    'client_id': client_id,
                    'business_type': data.get('business_type', 'individual'),
                    'tax_id': data.get('tax_id'),
                    'preferred_contact': data.get('preferred_contact', 'email'),
                    'filing_frequency': data.get('filing_frequency', 'annual'),
                    'portal_access': data.get('portal_access', False),
                    'notes': data.get('notes')
                }

                supabase.table('client_profiles')\
                    .insert(profile_data)\
                    .execute()

            return jsonify({
                'success': True,
                'data': client_result.data[0] if client_result.data else None
            })

    except Exception as e:
        logger.error(f"Error handling clients: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clients/<int:client_id>', methods=['PUT', 'DELETE'])
def client_operations(client_id):
    """Handle individual client operations"""
    global database_available

    if not database_available:
        return jsonify({'error': 'Database not available'}), 503

    try:
        supabase = get_supabase()

        if request.method == 'PUT':
            # Update client
            data = request.json

            # Update client record
            client_data = {
                'first_name': data.get('first_name'),
                'last_name': data.get('last_name'),
                'email': data.get('email'),
                'phone': data.get('phone')
            }

            client_result = supabase.table('clients')\
                .update(client_data)\
                .eq('id', client_id)\
                .execute()

            # Update or create profile
            profile_data = {
                'business_type': data.get('business_type'),
                'tax_id': data.get('tax_id'),
                'preferred_contact': data.get('preferred_contact'),
                'filing_frequency': data.get('filing_frequency'),
                'portal_access': data.get('portal_access'),
                'notes': data.get('notes')
            }

            # Try to update existing profile first
            profile_result = supabase.table('client_profiles')\
                .update(profile_data)\
                .eq('client_id', client_id)\
                .execute()

            # If no profile exists, create one
            if not profile_result.data:
                profile_data['client_id'] = client_id
                supabase.table('client_profiles')\
                    .insert(profile_data)\
                    .execute()

            return jsonify({
                'success': True,
                'data': client_result.data[0] if client_result.data else None
            })

        elif request.method == 'DELETE':
            # Delete client (cascading deletes will handle related records)
            result = supabase.table('clients')\
                .delete()\
                .eq('id', client_id)\
                .execute()

            return jsonify({
                'success': True,
                'message': 'Client deleted successfully'
            })

    except Exception as e:
        logger.error(f"Error handling client operations: {e}")
        return jsonify({'error': str(e)}), 500

# Enhanced route for documents page
@app.route('/documents/advanced')
def documents_advanced():
    """Render the enhanced documents page"""
    return render_template('documents_advanced.html')

# Enhanced route for client dashboard
@app.route('/clients/dashboard')
def client_dashboard():
    """Render the client dashboard page"""
    return render_template('client_dashboard.html')

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