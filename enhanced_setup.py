#!/usr/bin/env python3
"""
Enhanced Dixii Processor Setup Script
=====================================

This script sets up the enhanced tax document processing system with:
- Enhanced Claude OCR integration
- Advanced entity recognition
- Smart filename generation
- Comprehensive error handling
- Performance optimizations

Usage:
    python enhanced_setup.py [--quick] [--api-key YOUR_API_KEY]
"""

import os
import sys
import argparse
import logging
from pathlib import Path
import subprocess
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EnhancedSetup:
    def __init__(self, api_key=None, quick_setup=False):
        self.api_key = api_key
        self.quick_setup = quick_setup
        self.project_root = Path(__file__).parent
        
        # Required directories
        self.directories = [
            'uploads',
            'processed',
            'models',
            'utils',
            'templates',
            'logs'
        ]
        
        # Required files
        self.required_files = {
            'models/__init__.py': '',
            'utils/__init__.py': '',
            '.env': self._generate_env_template(),
            'config.py': None,  # Will be handled separately
            'enhanced_app.py': None,
        }
        
        # Enhanced components
        self.enhanced_components = [
            'models/enhanced_claude_ocr.py',
            'utils/entity_recognizer.py',
            'utils/filename_generator.py',
            'utils/enhanced_file_processor.py',
            'templates/enhanced_index.html'
        ]
    
    def setup(self):
        """Run the complete enhanced setup process"""
        logger.info("🚀 Starting Enhanced Dixii Processor Setup")
        
        try:
            self._check_python_version()
            self._create_directories()
            self._install_dependencies()
            self._create_required_files()
            self._verify_enhanced_components()
            self._setup_configuration()
            self._validate_setup()
            
            logger.info("✅ Enhanced setup completed successfully!")
            self._print_next_steps()
            
        except Exception as e:
            logger.error(f"❌ Setup failed: {e}")
            sys.exit(1)
    
    def _check_python_version(self):
        """Check Python version compatibility"""
        logger.info("🐍 Checking Python version...")
        
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            raise RuntimeError("Python 3.8 or higher is required")
        
        logger.info(f"✅ Python {version.major}.{version.minor}.{version.micro} is compatible")
    
    def _create_directories(self):
        """Create necessary directories"""
        logger.info("📁 Creating project directories...")
        
        for directory in self.directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(exist_ok=True)
            logger.info(f"   Created: {directory}")
        
        # Create client folder examples
        processed_path = self.project_root / 'processed'
        example_folders = [
            'John_Smith',
            'ABC_Company_LLC',
            'Smith_Family_Trust'
        ]
        
        for folder in example_folders:
            (processed_path / folder).mkdir(exist_ok=True)
    
    def _install_dependencies(self):
        """Install required Python packages"""
        if self.quick_setup:
            logger.info("⚡ Quick setup: Skipping dependency installation")
            return
        
        logger.info("📦 Installing dependencies...")
        
        requirements_file = self.project_root / 'requirements.txt'
        if not requirements_file.exists():
            logger.warning("requirements.txt not found, creating basic version")
            self._create_basic_requirements()
        
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)
            ])
            logger.info("✅ Dependencies installed successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e}")
            raise
    
    def _create_required_files(self):
        """Create required files if they don't exist"""
        logger.info("📄 Creating required files...")
        
        for file_path, content in self.required_files.items():
            full_path = self.project_root / file_path
            
            if not full_path.exists() and content is not None:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)
                logger.info(f"   Created: {file_path}")
    
    def _verify_enhanced_components(self):
        """Verify that enhanced components exist"""
        logger.info("🔍 Verifying enhanced components...")
        
        missing_components = []
        for component in self.enhanced_components:
            component_path = self.project_root / component
            if not component_path.exists():
                missing_components.append(component)
        
        if missing_components:
            logger.warning("⚠️  Missing enhanced components:")
            for component in missing_components:
                logger.warning(f"   - {component}")
            logger.warning("Some advanced features may not be available")
        else:
            logger.info("✅ All enhanced components found")
    
    def _setup_configuration(self):
        """Setup configuration files"""
        logger.info("⚙️  Setting up configuration...")
        
        # Update .env file with API key if provided
        env_path = self.project_root / '.env'
        if self.api_key:
            env_content = env_path.read_text() if env_path.exists() else ""
            
            # Update or add API key
            lines = env_content.split('\n')
            api_key_found = False
            
            for i, line in enumerate(lines):
                if line.startswith('ANTHROPIC_API_KEY='):
                    lines[i] = f'ANTHROPIC_API_KEY={self.api_key}'
                    api_key_found = True
                    break
            
            if not api_key_found:
                lines.append(f'ANTHROPIC_API_KEY={self.api_key}')
            
            env_path.write_text('\n'.join(lines))
            logger.info("✅ Claude API key configured")
        else:
            logger.info("ℹ️  No API key provided - remember to set ANTHROPIC_API_KEY in .env")
    
    def _validate_setup(self):
        """Validate the setup by running basic tests"""
        logger.info("🧪 Validating setup...")
        
        try:
            # Test imports
            sys.path.insert(0, str(self.project_root))
            
            from config import Config
            logger.info("✅ Configuration module imported successfully")
            
            # Check if enhanced components can be imported
            enhanced_imports = [
                ('models.enhanced_claude_ocr', 'EnhancedClaudeOCR'),
                ('utils.entity_recognizer', 'EntityRecognizer'),
                ('utils.filename_generator', 'FilenameGenerator'),
                ('utils.enhanced_file_processor', 'EnhancedTaxDocumentProcessor')
            ]
            
            for module_name, class_name in enhanced_imports:
                try:
                    module = __import__(module_name, fromlist=[class_name])
                    getattr(module, class_name)
                    logger.info(f"✅ {class_name} imported successfully")
                except ImportError as e:
                    logger.warning(f"⚠️  Could not import {class_name}: {e}")
            
        except Exception as e:
            logger.warning(f"⚠️  Validation warning: {e}")
    
    def _generate_env_template(self):
        """Generate .env file template"""
        return """# Enhanced Dixii Processor Configuration
# =======================================

# Claude API Configuration
ANTHROPIC_API_KEY=your_claude_api_key_here

# Flask Configuration
SECRET_KEY=your_secret_key_here
FLASK_ENV=development

# File Processing Configuration
MAX_UPLOAD_SIZE=16777216
ALLOWED_EXTENSIONS=pdf,png,jpg,jpeg,tiff,bmp

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/dixii_processor.log

# Enhanced Features Configuration
ENABLE_ENTITY_RECOGNITION=true
ENABLE_SMART_FILENAME_GENERATION=true
ENABLE_ADVANCED_OCR=true

# Performance Configuration
MAX_CONCURRENT_PROCESSES=4
PROCESSING_TIMEOUT=300
"""
    
    def _create_basic_requirements(self):
        """Create basic requirements.txt if missing"""
        requirements_content = """flask==3.0.0
torch>=2.0.0
transformers>=4.35.0
Pillow>=10.0.0
anthropic>=0.25.0
python-multipart>=0.0.6
werkzeug>=3.0.0
pytesseract>=0.3.10
opencv-python>=4.8.0
numpy>=1.24.0
requests>=2.31.0
python-dotenv>=1.0.0
safetensors>=0.4.0
pdf2image>=1.16.0
"""
        requirements_path = self.project_root / 'requirements.txt'
        requirements_path.write_text(requirements_content)
        logger.info("Created basic requirements.txt")
    
    def _print_next_steps(self):
        """Print next steps for the user"""
        print("\n" + "="*60)
        print("🎉 ENHANCED DIXII PROCESSOR SETUP COMPLETE!")
        print("="*60)
        print("\n📋 Next Steps:")
        print("\n1. 🔑 Set up your Claude API key:")
        print("   - Get an API key from https://console.anthropic.com/")
        print("   - Add it to your .env file: ANTHROPIC_API_KEY=your_key_here")
        print("   - Or use the web interface Settings menu")
        
        print("\n2. 🚀 Start the enhanced application:")
        print("   python enhanced_app.py")
        print("   # or for development:")
        print("   python -m flask --app enhanced_app run --debug")
        
        print("\n3. 🌐 Open your browser:")
        print("   http://localhost:8080")
        
        print("\n4. 📖 Key Features Available:")
        print("   ✨ Smart Entity Recognition (LLC, Corp, Trust, Individual)")
        print("   🔍 Form-Specific Extraction (K-1, 1099, W-2, 1098, 1040)")
        print("   📝 Intelligent Filename Generation")
        print("   🤖 Advanced Amendment Detection")
        print("   📊 Enhanced Progress Tracking")
        print("   📁 Case-Insensitive Client Matching")
        
        print("\n5. 📚 Documentation:")
        print("   - Check README.md for detailed usage instructions")
        print("   - View setup_instructions.md for troubleshooting")
        
        print("\n6. 🧪 Test the System:")
        print("   - Upload sample tax documents")
        print("   - Try both auto and manual processing modes")
        print("   - Verify entity recognition and filename generation")
        
        if not self.api_key:
            print("\n⚠️  IMPORTANT: Remember to set your Claude API key!")
            print("   The system will work with limited functionality without it.")
        
        print("\n" + "="*60)

def main():
    """Main setup function"""
    parser = argparse.ArgumentParser(
        description="Enhanced Dixii Processor Setup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--api-key',
        help='Claude API key to configure automatically'
    )
    
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick setup (skip dependency installation)'
    )
    
    args = parser.parse_args()
    
    setup = EnhancedSetup(
        api_key=args.api_key,
        quick_setup=args.quick
    )
    
    setup.setup()

if __name__ == '__main__':
    main() 