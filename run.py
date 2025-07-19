#!/usr/bin/env python3
"""
Simple runner for the Tax Document Sorter application
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sys

# Add the project directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the main app
from app import app, is_port_in_use, find_free_port

def main():
    """Main function to run the application"""
    print("=" * 50)
    print("Tax Document Sorter - Debug Runner")
    print("=" * 50)

    # Check if port 5000 is available, otherwise find a free port
    if is_port_in_use(5000):
        port = find_free_port()
        print(f"Port 5000 in use, starting on port {port}")
    else:
        port = 5000
        print(f"Starting on port {port}")

    print(f"Access the application at: http://localhost:{port}")
    print("=" * 50)

    try:
        app.run(
            debug=True,
            host='0.0.0.0',
            port=port,
            use_reloader=False,  # Disable reloader to avoid issues
            threaded=True
        )
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
    except Exception as e:
        print(f"Error starting application: {e}")
        return 1

    return 0

if __name__ == '__main__':
    exit(main())