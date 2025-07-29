#!/usr/bin/env python3
"""
Quick Fix Script for DIXII Processing System
Addresses immediate issues with name detection and processing
"""

import os
import sys
import logging
import shutil
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_permissions():
    """Fix file permissions"""
    logger.info("Fixing file permissions...")
    
    directories = ['uploads', 'processed', 'models']
    
    for directory in directories:
        try:
            os.chmod(directory, 0o755)
            logger.info(f"✓ Fixed permissions for {directory}")
        except Exception as e:
            logger.error(f"✗ Failed to fix permissions for {directory}: {e}")

def clear_temp_files():
    """Clear temporary files that might be causing issues"""
    logger.info("Clearing temporary files...")
    
    temp_patterns = [
        'uploads/*.tmp',
        'uploads/*.temp',
        'processed/*.tmp',
        'processed/*.temp',
        '/tmp/dixii_*'
    ]
    
    for pattern in temp_patterns:
        try:
            import glob
            files = glob.glob(pattern)
            for file in files:
                try:
                    os.remove(file)
                    logger.info(f"✓ Removed temp file: {file}")
                except:
                    pass
        except Exception as e:
            logger.warning(f"Could not clear pattern {pattern}: {e}")

def reset_sessions():
    """Reset processing sessions"""
    logger.info("Resetting processing sessions...")
    
    try:
        # Clear session data from memory (if running)
        import requests
        try:
            response = requests.post('http://localhost:5000/api/cleanup-sessions')
            if response.status_code == 200:
                logger.info("✓ Cleared sessions via API")
            else:
                logger.warning("Could not clear sessions via API")
        except:
            logger.warning("Could not connect to API for session cleanup")
    except ImportError:
        logger.warning("requests not available for API cleanup")

def check_and_fix_tesseract():
    """Check and fix tesseract installation"""
    logger.info("Checking tesseract installation...")
    
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        logger.info(f"✓ Tesseract version: {version}")
        return True
    except Exception as e:
        logger.error(f"✗ Tesseract error: {e}")
        logger.info("Please install tesseract:")
        logger.info("  macOS: brew install tesseract")
        logger.info("  Ubuntu: sudo apt-get install tesseract-ocr")
        logger.info("  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        return False

def fix_config():
    """Fix configuration issues"""
    logger.info("Checking configuration...")
    
    try:
        from config import Config
        
        # Create .env file if it doesn't exist
        env_file = Path('.env')
        if not env_file.exists():
            logger.info("Creating .env file...")
            with open('.env', 'w') as f:
                f.write("# DIXII Configuration\n")
                f.write("# Add your API keys here\n")
                f.write("ANTHROPIC_API_KEY=your_api_key_here\n")
                f.write("SECRET_KEY=your_secret_key_here\n")
            logger.info("✓ Created .env file")
            logger.info("⚠ Please add your API keys to .env file")
        
        # Ensure directories exist
        for directory in ['uploads', 'processed']:
            Path(directory).mkdir(exist_ok=True)
            logger.info(f"✓ Ensured directory exists: {directory}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Configuration error: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality"""
    logger.info("Testing basic functionality...")
    
    try:
        # Test imports
        from models.enhanced_name_detector import EnhancedNameDetector
        from utils.document_type_aware_preprocessor import DocumentTypeAwarePreprocessor
        from utils.enhanced_file_processor import EnhancedTaxDocumentProcessor
        
        logger.info("✓ All core modules imported successfully")
        
        # Test basic initialization
        detector = EnhancedNameDetector()
        preprocessor = DocumentTypeAwarePreprocessor()
        
        logger.info("✓ Core components initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Basic functionality test failed: {e}")
        return False

def create_test_files():
    """Create test files for debugging"""
    logger.info("Creating test files...")
    
    # Create a simple test image
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Create a simple test image
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add some text
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        draw.text((50, 50), "Test Document", fill='black', font=font)
        draw.text((50, 100), "Client: John Doe", fill='black', font=font)
        draw.text((50, 150), "Document Type: W-2", fill='black', font=font)
        
        test_image_path = "test_document.png"
        img.save(test_image_path)
        logger.info(f"✓ Created test image: {test_image_path}")
        
        return test_image_path
        
    except Exception as e:
        logger.error(f"✗ Failed to create test image: {e}")
        return None

def run_quick_fix():
    """Run all quick fixes"""
    logger.info("Starting Quick Fix for DIXII Processing System...")
    logger.info("=" * 50)
    
    fixes = [
        ("File Permissions", fix_permissions),
        ("Clear Temp Files", clear_temp_files),
        ("Reset Sessions", reset_sessions),
        ("Tesseract Check", check_and_fix_tesseract),
        ("Configuration", fix_config),
        ("Basic Functionality", test_basic_functionality)
    ]
    
    results = {}
    
    for fix_name, fix_func in fixes:
        logger.info(f"\n--- {fix_name} ---")
        try:
            results[fix_name] = fix_func()
        except Exception as e:
            logger.error(f"✗ {fix_name} failed with exception: {e}")
            results[fix_name] = False
    
    # Create test files
    logger.info("\n--- Create Test Files ---")
    test_file = create_test_files()
    if test_file:
        results["Test Files"] = True
        logger.info(f"✓ Test file created: {test_file}")
    else:
        results["Test Files"] = False
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("QUICK FIX SUMMARY")
    logger.info("=" * 50)
    
    passed = 0
    total = len(results)
    
    for fix_name, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"{fix_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} fixes applied successfully")
    
    if passed == total:
        logger.info("🎉 All quick fixes applied successfully!")
        logger.info("Try running the system again.")
    else:
        logger.error("❌ Some fixes failed. Please review the issues above.")
        logger.info("Run the health check for more details: python test_system_health.py")
    
    return passed == total

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Quick Fix Script for DIXII Processing System")
        print("Usage: python quick_fix.py")
        print("This script attempts to fix common issues with the processing system.")
        sys.exit(0)
    
    success = run_quick_fix()
    
    if not success:
        logger.info("\nNext steps:")
        logger.info("1. Run: python test_system_health.py")
        logger.info("2. Check: TROUBLESHOOTING_GUIDE.md")
        logger.info("3. Verify API keys in .env file")
        logger.info("4. Test with sample files")
        sys.exit(1)
    else:
        logger.info("\nQuick fix completed! System should be ready.")
        sys.exit(0)

if __name__ == "__main__":
    main() 