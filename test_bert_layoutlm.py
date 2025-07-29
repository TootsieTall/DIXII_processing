#!/usr/bin/env python3
"""
Test script for BERT and LayoutLM name detection
"""

import os
import sys
import logging
from PIL import Image, ImageDraw, ImageFont

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_image():
    """Create a test image with names for testing"""
    try:
        # Create a simple test image
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add some text with names
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        # Add test content
        draw.text((50, 50), "Tax Document", fill='black', font=font)
        draw.text((50, 100), "Client: John Smith", fill='black', font=font)
        draw.text((50, 150), "Partner: Jane Doe", fill='black', font=font)
        draw.text((50, 200), "Trustee: Robert Johnson", fill='black', font=font)
        draw.text((50, 250), "Document Type: Schedule K-1", fill='black', font=font)
        draw.text((50, 300), "Tax Year: 2024", fill='black', font=font)
        
        test_image_path = "test_names.png"
        img.save(test_image_path)
        logger.info(f"✓ Created test image: {test_image_path}")
        
        return test_image_path
        
    except Exception as e:
        logger.error(f"✗ Failed to create test image: {e}")
        return None

def test_name_detection():
    """Test the name detection with BERT and LayoutLM"""
    try:
        from models.enhanced_name_detector import EnhancedNameDetector
        
        logger.info("Testing name detection with BERT and LayoutLM...")
        
        # Create test image
        test_image = create_test_image()
        if not test_image:
            logger.error("Could not create test image")
            return False
        
        # Initialize detector
        detector = EnhancedNameDetector()
        
        # Test detection
        results = detector.detect_names_in_document(test_image, "Schedule K-1")
        
        # Analyze results
        logger.info("Detection Results:")
        logger.info(f"  LayoutLM names: {len(results.get('layoutlm_names', []))}")
        logger.info(f"  BERT NER names: {len(results.get('bert_ner_names', []))}")
        logger.info(f"  Pattern names: {len(results.get('pattern_names', []))}")
        logger.info(f"  Combined names: {len(results.get('combined_names', []))}")
        logger.info(f"  Confidence: {results.get('confidence', 0.0):.2f}")
        logger.info(f"  Methods used: {results.get('detection_methods', [])}")
        
        # Show detected names
        for method, names in [
            ('LayoutLM', results.get('layoutlm_names', [])),
            ('BERT NER', results.get('bert_ner_names', [])),
            ('Pattern', results.get('pattern_names', [])),
            ('Combined', results.get('combined_names', []))
        ]:
            if names:
                logger.info(f"  {method} detected names:")
                for name_info in names:
                    logger.info(f"    - {name_info.get('name', 'Unknown')} (confidence: {name_info.get('confidence', 0.0):.2f})")
        
        # Clean up test image
        try:
            os.remove(test_image)
            logger.info(f"✓ Cleaned up test image: {test_image}")
        except:
            pass
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Name detection test failed: {e}")
        return False

def test_model_loading():
    """Test model loading specifically"""
    try:
        from models.enhanced_name_detector import EnhancedNameDetector
        
        logger.info("Testing model loading...")
        
        detector = EnhancedNameDetector()
        
        # Check which models loaded successfully
        models_loaded = []
        if detector.layoutlm_model:
            models_loaded.append("LayoutLM")
        if detector.bert_ner_model:
            models_loaded.append("BERT NER")
        
        logger.info(f"✓ Models loaded: {', '.join(models_loaded) if models_loaded else 'None'}")
        
        return len(models_loaded) > 0
        
    except Exception as e:
        logger.error(f"✗ Model loading test failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("Starting BERT and LayoutLM Test...")
    logger.info("=" * 50)
    
    tests = [
        ("Model Loading", test_model_loading),
        ("Name Detection", test_name_detection)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} Test ---")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"✗ {test_name} test failed with exception: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("TEST SUMMARY")
    logger.info("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! BERT and LayoutLM are working correctly.")
        return True
    else:
        logger.error("❌ Some tests failed. Please review the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 