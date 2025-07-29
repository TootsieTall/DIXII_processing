#!/usr/bin/env python3
"""
DIXII Processing System Health Check
Diagnoses common issues with the name detection and processing system
"""

import os
import sys
import logging
import traceback
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if all required dependencies are installed"""
    logger.info("Checking dependencies...")
    
    required_packages = [
        'torch', 'transformers', 'PIL', 'pytesseract', 'numpy',
        'flask', 'anthropic', 'pdf2image', 'cv2'  # Changed from opencv-python to cv2
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            logger.info(f"✓ {package}")
        except ImportError:
            missing_packages.append(package)
            logger.error(f"✗ {package} - MISSING")
    
    if missing_packages:
        logger.error(f"Missing packages: {missing_packages}")
        logger.info("Install with: pip install " + " ".join(missing_packages))
        return False
    
    return True

def check_tesseract():
    """Check if tesseract is properly installed"""
    logger.info("Checking tesseract installation...")
    
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        logger.info(f"✓ Tesseract version: {version}")
        return True
    except Exception as e:
        logger.error(f"✗ Tesseract error: {e}")
        logger.info("Install tesseract: https://github.com/tesseract-ocr/tesseract")
        return False

def check_directories():
    """Check if required directories exist and are writable"""
    logger.info("Checking directories...")
    
    directories = ['uploads', 'processed', 'models']
    
    for directory in directories:
        path = Path(directory)
        if path.exists():
            if os.access(path, os.W_OK):
                logger.info(f"✓ {directory} - exists and writable")
            else:
                logger.error(f"✗ {directory} - exists but not writable")
                return False
        else:
            try:
                path.mkdir(parents=True, exist_ok=True)
                logger.info(f"✓ {directory} - created")
            except Exception as e:
                logger.error(f"✗ {directory} - cannot create: {e}")
                return False
    
    return True

def check_config():
    """Check configuration settings"""
    logger.info("Checking configuration...")
    
    try:
        from config import Config
        
        # Check API key
        if not Config.ANTHROPIC_API_KEY:
            logger.warning("⚠ ANTHROPIC_API_KEY not set")
        else:
            logger.info("✓ ANTHROPIC_API_KEY configured")
        
        # Check model path
        if Config.DONUT_MODEL_PATH:
            logger.info(f"✓ DONUT_MODEL_PATH: {Config.DONUT_MODEL_PATH}")
        else:
            logger.warning("⚠ DONUT_MODEL_PATH not configured")
        
        return True
    except Exception as e:
        logger.error(f"✗ Configuration error: {e}")
        return False

def test_name_detection():
    """Test name detection functionality"""
    logger.info("Testing name detection...")
    
    try:
        from models.enhanced_name_detector import EnhancedNameDetector
        
        detector = EnhancedNameDetector()
        logger.info("✓ EnhancedNameDetector initialized")
        
        # Test with a simple case
        test_results = detector.detect_names_in_document("test_image.jpg", "W-2")
        if isinstance(test_results, dict):
            logger.info("✓ Name detection test passed")
            return True
        else:
            logger.error("✗ Name detection returned invalid format")
            return False
            
    except Exception as e:
        logger.error(f"✗ Name detection test failed: {e}")
        return False

def test_document_preprocessing():
    """Test document preprocessing functionality"""
    logger.info("Testing document preprocessing...")
    
    try:
        from utils.document_type_aware_preprocessor import DocumentTypeAwarePreprocessor
        
        preprocessor = DocumentTypeAwarePreprocessor()
        logger.info("✓ DocumentTypeAwarePreprocessor initialized")
        
        # Test with a simple case
        test_results = preprocessor.preprocess_document("test_image.jpg", "W-2", 0.8)
        if isinstance(test_results, dict):
            logger.info("✓ Document preprocessing test passed")
            return True
        else:
            logger.error("✗ Document preprocessing returned invalid format")
            return False
            
    except Exception as e:
        logger.error(f"✗ Document preprocessing test failed: {e}")
        return False

def test_file_processor():
    """Test file processor functionality"""
    logger.info("Testing file processor...")
    
    try:
        from utils.enhanced_file_processor import EnhancedTaxDocumentProcessor
        
        # Initialize with dummy values for testing
        processor = EnhancedTaxDocumentProcessor("dummy_model_path", "dummy_api_key")
        logger.info("✓ EnhancedTaxDocumentProcessor initialized")
        return True
        
    except Exception as e:
        logger.error(f"✗ File processor test failed: {e}")
        return False

def check_model_files():
    """Check if model files exist"""
    logger.info("Checking model files...")
    
    model_files = [
        'models/__init__.py',
        'models/enhanced_name_detector.py',
        'models/enhanced_claude_ocr.py',
        'models/donut_classifier.py'
    ]
    
    missing_files = []
    
    for file_path in model_files:
        if os.path.exists(file_path):
            logger.info(f"✓ {file_path}")
        else:
            missing_files.append(file_path)
            logger.error(f"✗ {file_path} - MISSING")
    
    if missing_files:
        logger.error(f"Missing model files: {missing_files}")
        return False
    
    return True

def run_health_check():
    """Run complete health check"""
    logger.info("Starting DIXII Processing System Health Check...")
    logger.info("=" * 50)
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Tesseract", check_tesseract),
        ("Directories", check_directories),
        ("Configuration", check_config),
        ("Model Files", check_model_files),
        ("Name Detection", test_name_detection),
        ("Document Preprocessing", test_document_preprocessing),
        ("File Processor", test_file_processor)
    ]
    
    results = {}
    
    for check_name, check_func in checks:
        logger.info(f"\n--- {check_name} Check ---")
        try:
            results[check_name] = check_func()
        except Exception as e:
            logger.error(f"✗ {check_name} check failed with exception: {e}")
            results[check_name] = False
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("HEALTH CHECK SUMMARY")
    logger.info("=" * 50)
    
    passed = 0
    total = len(results)
    
    for check_name, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"{check_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} checks passed")
    
    if passed == total:
        logger.info("🎉 All checks passed! System is healthy.")
        return True
    else:
        logger.error("❌ Some checks failed. Please review the issues above.")
        return False

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--verbose":
        logging.getLogger().setLevel(logging.DEBUG)
    
    success = run_health_check()
    
    if not success:
        logger.info("\nTroubleshooting tips:")
        logger.info("1. Check the TROUBLESHOOTING_GUIDE.md for detailed solutions")
        logger.info("2. Verify all dependencies are installed: pip install -r requirements.txt")
        logger.info("3. Check file permissions and directory access")
        logger.info("4. Verify API keys and configuration settings")
        logger.info("5. Test with sample files to isolate issues")
        sys.exit(1)
    else:
        logger.info("\nSystem is ready for processing!")
        sys.exit(0)

if __name__ == "__main__":
    main() 