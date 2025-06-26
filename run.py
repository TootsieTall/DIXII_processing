#!/usr/bin/env python3
"""
Tax Document Sorter - Startup Script
"""

import os
import sys
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        'flask',
        'torch', 
        'transformers',
        'anthropic',
        'PIL',
        'pdf2image'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n💡 Please install dependencies:")
        print("   pip install -r requirements.txt")
        return False
    
    return True

def check_api_key():
    """Check if Claude API key is configured"""
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key or api_key == 'your_claude_api_key_here':
        print("❌ Claude API key not configured")
        print("\n💡 Please create a .env file with your API key:")
        print("   ANTHROPIC_API_KEY=your_actual_api_key_here")
        print("\n🔗 Get your API key at: https://console.anthropic.com/")
        return False
    
    return True

def check_donut_model():
    """Check if Donut model is available"""
    model_path = Path('./donut-irs-tax-docs-classifier')
    if not model_path.exists():
        print("❌ Donut model not found")
        print("\n💡 Please clone the model repository:")
        print("   git lfs install")
        print("   git clone https://huggingface.co/hsarfraz/donut-irs-tax-docs-classifier")
        return False
    
    return True

def create_directories():
    """Create necessary directories"""
    directories = ['uploads', 'processed', 'models', 'utils', 'templates']
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)

def main():
    """Main startup function"""
    print("🚀 Tax Document Sorter - Starting Up...")
    print("=" * 50)
    
    # Check dependencies
    print("📦 Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)
    print("✅ Dependencies OK")
    
    # Check API key
    print("🔑 Checking API configuration...")
    if not check_api_key():
        sys.exit(1)
    print("✅ API key configured")
    
    # Check Donut model
    print("🤖 Checking Donut model...")
    if not check_donut_model():
        sys.exit(1)
    print("✅ Donut model found")
    
    # Create directories
    print("📁 Creating directories...")
    create_directories()
    print("✅ Directories ready")
    
    print("=" * 50)
    print("🎉 All checks passed! Starting application...")
    print("🌐 Application will be available at: http://localhost:8080")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Import and run the Flask app
    try:
        from app import app, init_processor
        if init_processor():
            app.run(debug=False, host='0.0.0.0', port=8080)
        else:
            print("❌ Failed to initialize document processor")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 