#!/usr/bin/env python3
"""
Debug server to test specific endpoints
"""

from flask import Flask, render_template, request, jsonify
import os
import traceback

app = Flask(__name__)

@app.route('/')
def index():
    """Test main page"""
    try:
        return render_template('index.html')
    except Exception as e:
        return jsonify({'error': f'Template error: {str(e)}', 'trace': traceback.format_exc()}), 500

@app.route('/favicon.ico')
def favicon():
    """Serve favicon to prevent 404 errors"""
    return '', 204

@app.route('/upload', methods=['POST'])
def upload_test():
    """Test upload endpoint"""
    try:
        # Basic validation
        if 'files' not in request.files:
            return jsonify({'error': 'No files uploaded'}), 400

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': 'No files selected'}), 400

        # Return success without processing
        return jsonify({
            'success': True,
            'session_id': 'debug-session-123',
            'message': f'Received {len(files)} files for testing'
        })

    except Exception as e:
        return jsonify({
            'error': f'Upload error: {str(e)}',
            'trace': traceback.format_exc()
        }), 500

@app.route('/status/<session_id>')
def status_test(session_id):
    """Test status endpoint"""
    return jsonify({
        'status': 'completed',
        'total': 2,
        'current': 2,
        'message': 'Debug status'
    })

@app.route('/api/preview-files/<session_id>')
def preview_files_test(session_id):
    """Test preview files endpoint"""
    return jsonify({
        'success': True,
        'files': [
            {
                'original_filename': 'test1.pdf',
                'new_filename': 'Test Document 1.pdf',
                'processed_path': 'test/Test Document 1.pdf',
                'document_type': 'W-2',
                'client_name': 'Test Client',
                'tax_year': '2024',
                'file_type': 'pdf'
            }
        ]
    })

def find_free_port():
    """Find a free port"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def is_port_in_use(port):
    """Check if port is in use"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('', port))
            return False
        except OSError:
            return True

if __name__ == '__main__':
    # Find available port
    if is_port_in_use(5000):
        port = find_free_port()
        print(f"Port 5000 in use, using port {port}")
    else:
        port = 5000
        print(f"Using port {port}")

    print(f"Debug server running at: http://localhost:{port}")
    print("Testing basic endpoints without full AI processing...")

    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)