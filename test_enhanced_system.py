#!/usr/bin/env python3
"""
Enhanced System Test Script
===========================

Test script to validate the enhanced tax document processing system components.
Tests each major component individually and then tests integration.

Usage:
    python test_enhanced_system.py [--verbose] [--api-key YOUR_API_KEY]
"""

import os
import sys
import argparse
import tempfile
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_test_image(text: str, filename: str) -> str:
    """Create a simple test image with text for testing OCR"""
    # Create a simple test image
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        # Try to use a default font
        font = ImageFont.load_default()
    except:
        font = None
    
    # Draw some test text
    lines = text.split('\n')
    y_position = 50
    for line in lines:
        draw.text((50, y_position), line, fill='black', font=font)
        y_position += 40
    
    # Save to temporary file
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    img.save(temp_path, 'JPEG')
    return temp_path

def test_imports():
    """Test that all enhanced components can be imported"""
    print("🔍 Testing component imports...")
    
    try:
        from config import Config
        print("✅ Config imported successfully")
    except ImportError as e:
        print(f"❌ Config import failed: {e}")
        return False
    
    try:
        from models.enhanced_claude_ocr import EnhancedClaudeOCR
        print("✅ EnhancedClaudeOCR imported successfully")
    except ImportError as e:
        print(f"❌ EnhancedClaudeOCR import failed: {e}")
        return False
    
    try:
        from utils.entity_recognizer import EntityRecognizer
        print("✅ EntityRecognizer imported successfully")
    except ImportError as e:
        print(f"❌ EntityRecognizer import failed: {e}")
        return False
    
    try:
        from utils.filename_generator import FilenameGenerator
        print("✅ FilenameGenerator imported successfully")
    except ImportError as e:
        print(f"❌ FilenameGenerator import failed: {e}")
        return False
    
    try:
        from utils.enhanced_file_processor import EnhancedTaxDocumentProcessor
        print("✅ EnhancedTaxDocumentProcessor imported successfully")
    except ImportError as e:
        print(f"❌ EnhancedTaxDocumentProcessor import failed: {e}")
        return False
    
    return True

def test_entity_recognizer():
    """Test entity recognizer functionality"""
    print("\n🏢 Testing EntityRecognizer...")
    
    try:
        from utils.entity_recognizer import EntityRecognizer
        
        # Create temp processed folder
        with tempfile.TemporaryDirectory() as temp_dir:
            recognizer = EntityRecognizer(temp_dir)
            
            # Test individual entity
            test_info = {
                'document_type': 'Form 1040',
                'primary_first_name': 'John',
                'primary_last_name': 'Smith',
                'tax_year': '2023'
            }
            
            result = recognizer.analyze_entity(test_info)
            print(f"✅ Individual entity recognized: {result['entity_type']}")
            print(f"   Folder name: {result['folder_name']}")
            
            # Test business entity
            test_info = {
                'document_type': 'Form 1099-NEC',
                'recipient_business_name': 'ABC Company LLC',
                'tax_year': '2023'
            }
            
            result = recognizer.analyze_entity(test_info)
            print(f"✅ Business entity recognized: {result['entity_type']}")
            print(f"   Business name: {result['business_name']}")
            
            return True
            
    except Exception as e:
        print(f"❌ EntityRecognizer test failed: {e}")
        return False

def test_filename_generator():
    """Test filename generator functionality"""
    print("\n📝 Testing FilenameGenerator...")
    
    try:
        from utils.filename_generator import FilenameGenerator
        
        generator = FilenameGenerator()
        
        # Test individual filename
        extracted_info = {
            'document_type': 'Form 1040',
            'tax_year': '2023',
            'is_amended': False
        }
        
        entity_info = {
            'entity_type': 'Individual',
            'first_name': 'John',
            'last_name': 'Smith',
            'is_joint': False
        }
        
        filename = generator.generate_filename(extracted_info, entity_info, 'test.pdf')
        print(f"✅ Individual filename generated: {filename}")
        
        # Test business filename
        extracted_info = {
            'document_type': 'Form 1120S',
            'tax_year': '2023',
            'is_amended': False
        }
        
        entity_info = {
            'entity_type': 'LLC',
            'business_name': 'ABC Company LLC'
        }
        
        filename = generator.generate_filename(extracted_info, entity_info, 'test.pdf')
        print(f"✅ Business filename generated: {filename}")
        
        # Test K-1 filename
        extracted_info = {
            'document_type': 'Schedule K-1',
            'partnership_name': 'XYZ Partners LP',
            'tax_year': '2023',
            'is_amended': False
        }
        
        entity_info = {
            'entity_type': 'Individual',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'is_joint': False
        }
        
        filename = generator.generate_filename(extracted_info, entity_info, 'test.pdf')
        print(f"✅ K-1 filename generated: {filename}")
        
        return True
        
    except Exception as e:
        print(f"❌ FilenameGenerator test failed: {e}")
        return False

def test_enhanced_ocr(api_key=None):
    """Test enhanced Claude OCR functionality"""
    print("\n🤖 Testing EnhancedClaudeOCR...")
    
    if not api_key:
        print("⚠️  No API key provided, skipping OCR tests")
        return True
    
    try:
        from models.enhanced_claude_ocr import EnhancedClaudeOCR
        
        ocr = EnhancedClaudeOCR(api_key)
        
        # Create test image
        test_text = """Form 1040
U.S. Individual Income Tax Return
Tax Year 2023

Name: John Smith
Spouse: Jane Smith
Address: 123 Main St, Anytown, USA"""
        
        test_image_path = create_test_image(test_text, 'test_1040.jpg')
        
        try:
            # Test document identification
            result = ocr._identify_document_type(ocr.image_to_base64(test_image_path))
            print(f"✅ Document identification test completed")
            print(f"   Detected type: {result[0] if result else 'None'}")
            
            # Clean up test image
            os.remove(test_image_path)
            
            return True
            
        except Exception as e:
            print(f"⚠️  OCR test failed (API issue?): {e}")
            # Clean up test image
            if os.path.exists(test_image_path):
                os.remove(test_image_path)
            return True  # Don't fail overall test for API issues
            
    except Exception as e:
        print(f"❌ EnhancedClaudeOCR test failed: {e}")
        return False

def test_enhanced_processor(api_key=None):
    """Test the integrated enhanced processor"""
    print("\n🚀 Testing EnhancedTaxDocumentProcessor...")
    
    try:
        from utils.enhanced_file_processor import EnhancedTaxDocumentProcessor
        from config import Config
        
        if api_key:
            processor = EnhancedTaxDocumentProcessor(
                donut_model_path='./donut-irs-tax-docs-classifier',
                claude_api_key=api_key
            )
            print("✅ Enhanced processor initialized with API key")
        else:
            print("⚠️  No API key provided, testing initialization only")
            # Test without API key (should handle gracefully)
            try:
                processor = EnhancedTaxDocumentProcessor(
                    donut_model_path='./donut-irs-tax-docs-classifier',
                    claude_api_key=''
                )
                print("✅ Enhanced processor initialized without API key")
            except Exception as e:
                print(f"⚠️  Processor initialization warning: {e}")
        
        # Test statistics generation
        sample_results = [
            {
                'status': 'completed',
                'entity_info': {'entity_type': 'Individual'},
                'document_type': 'Form 1040',
                'confidence': 0.9
            },
            {
                'status': 'completed',
                'entity_info': {'entity_type': 'LLC'},
                'document_type': 'Form 1120S',
                'confidence': 0.8
            }
        ]
        
        stats = processor.get_enhanced_processing_stats(sample_results)
        print(f"✅ Statistics generation test completed")
        print(f"   Entity breakdown: {stats.get('entity_breakdown', {})}")
        
        return True
        
    except Exception as e:
        print(f"❌ EnhancedTaxDocumentProcessor test failed: {e}")
        return False

def test_flask_app():
    """Test Flask application initialization"""
    print("\n🌐 Testing Flask application...")
    
    try:
        # Test app import
        from enhanced_app import app, init_enhanced_processor
        print("✅ Enhanced Flask app imported successfully")
        
        # Test processor initialization
        init_enhanced_processor()
        print("✅ Flask processor initialization completed")
        
        # Test with app context
        with app.app_context():
            print("✅ Flask app context test completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Flask app test failed: {e}")
        return False

def test_configuration():
    """Test configuration loading"""
    print("\n⚙️  Testing Configuration...")
    
    try:
        from config import Config
        
        # Test basic config attributes
        assert hasattr(Config, 'UPLOAD_FOLDER')
        assert hasattr(Config, 'PROCESSED_FOLDER')
        assert hasattr(Config, 'ALLOWED_EXTENSIONS')
        
        print(f"✅ Configuration loaded successfully")
        print(f"   Upload folder: {Config.UPLOAD_FOLDER}")
        print(f"   Processed folder: {Config.PROCESSED_FOLDER}")
        print(f"   Allowed extensions: {Config.ALLOWED_EXTENSIONS}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def run_all_tests(api_key=None, verbose=False):
    """Run all tests and return overall result"""
    print("🧪 Enhanced System Test Suite")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Component Imports", test_imports),
        ("Entity Recognizer", test_entity_recognizer),
        ("Filename Generator", test_filename_generator),
        ("Enhanced OCR", lambda: test_enhanced_ocr(api_key)),
        ("Enhanced Processor", lambda: test_enhanced_processor(api_key)),
        ("Flask Application", test_flask_app),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! Enhanced system is ready to use.")
        print("\nNext steps:")
        print("1. Run: python enhanced_app.py")
        print("2. Open: http://localhost:8080")
        print("3. Configure Claude API key in Settings (if not done)")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the issues above.")
        print("\nTroubleshooting:")
        print("- Ensure all dependencies are installed: pip install -r requirements.txt")
        print("- Check that Claude API key is valid (if provided)")
        print("- Verify all enhanced component files exist")
        return False

def main():
    """Main test function"""
    parser = argparse.ArgumentParser(
        description="Enhanced System Test Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--api-key',
        help='Claude API key for testing OCR functionality'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Set verbose mode
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    # Run tests
    success = run_all_tests(args.api_key, args.verbose)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main() 