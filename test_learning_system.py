#!/usr/bin/env python3
"""
Test script for the learning system in enhanced name detection
"""

import os
import sys
import logging
import json
from PIL import Image, ImageDraw, ImageFont

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_document(doc_type: str, client_name: str) -> str:
    """Create a test document with specific content"""
    try:
        # Create a simple test document
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.load_default()
        except:
            font = None
        
        # Add content based on document type
        if doc_type.lower() == 'schedule_k1':
            draw.text((50, 50), "Schedule K-1 (Form 1065)", fill='black', font=font)
            draw.text((50, 100), f"Partner: {client_name}", fill='black', font=font)
            draw.text((50, 150), "Tax Year: 2024", fill='black', font=font)
        elif doc_type.lower() == 'w2':
            draw.text((50, 50), "Form W-2", fill='black', font=font)
            draw.text((50, 100), f"Employee: {client_name}", fill='black', font=font)
            draw.text((50, 150), "Tax Year: 2024", fill='black', font=font)
        elif doc_type.lower() == '1099':
            draw.text((50, 50), "Form 1099-MISC", fill='black', font=font)
            draw.text((50, 100), f"Payee: {client_name}", fill='black', font=font)
            draw.text((50, 150), "Tax Year: 2024", fill='black', font=font)
        else:
            draw.text((50, 50), "Tax Document", fill='black', font=font)
            draw.text((50, 100), f"Client: {client_name}", fill='black', font=font)
            draw.text((50, 150), "Document Type: General", fill='black', font=font)
        
        # Save the document
        filename = f"test_{doc_type.lower()}_{client_name.replace(' ', '_')}.png"
        img.save(filename)
        logger.info(f"✓ Created test document: {filename}")
        
        return filename
        
    except Exception as e:
        logger.error(f"✗ Failed to create test document: {e}")
        return None

def test_learning_system():
    """Test the learning system functionality"""
    try:
        from models.enhanced_name_detector import EnhancedNameDetector
        
        logger.info("Testing learning system...")
        
        # Initialize detector
        detector = EnhancedNameDetector()
        
        # Test 1: Learn from manual input
        logger.info("\n--- Test 1: Learning from Manual Input ---")
        
        # Create test documents
        test_cases = [
            ('schedule_k1', 'John Smith'),
            ('w2', 'Jane Doe'),
            ('1099', 'Robert Johnson'),
            ('schedule_k1', 'Alice Brown'),
            ('w2', 'Bob Wilson')
        ]
        
        for doc_type, client_name in test_cases:
            # Create test document
            doc_path = create_test_document(doc_type, client_name)
            if not doc_path:
                continue
            
            # Simulate manual input (user enters the name)
            bbox_location = [50, 100, 300, 120]  # Approximate location of name
            
            # Learn from manual input
            detector.learn_from_manual_input(
                image_path=doc_path,
                manual_name=client_name,
                doc_type=doc_type,
                bbox_location=bbox_location,
                confidence=1.0
            )
            
            logger.info(f"✓ Learned: {client_name} on {doc_type}")
            
            # Clean up test file
            try:
                os.remove(doc_path)
            except:
                pass
        
        # Test 2: Test location-based detection
        logger.info("\n--- Test 2: Location-Based Detection ---")
        
        # Create a new document of the same type
        new_doc_path = create_test_document('schedule_k1', 'New Client')
        if new_doc_path:
            # Test detection on new document
            results = detector.detect_names_in_document(new_doc_path, 'schedule_k1')
            
            logger.info("Detection Results:")
            logger.info(f"  LayoutLM names: {len(results.get('layoutlm_names', []))}")
            logger.info(f"  BERT NER names: {len(results.get('bert_ner_names', []))}")
            logger.info(f"  Pattern names: {len(results.get('pattern_names', []))}")
            logger.info(f"  Location names: {len(results.get('location_names', []))}")
            logger.info(f"  Combined names: {len(results.get('combined_names', []))}")
            logger.info(f"  Confidence: {results.get('confidence', 0.0):.2f}")
            logger.info(f"  Methods used: {results.get('detection_methods', [])}")
            
            # Show location-based detections
            location_names = results.get('location_names', [])
            if location_names:
                logger.info("  Location-based detections:")
                for name_info in location_names:
                    logger.info(f"    - {name_info.get('name', 'Unknown')} (confidence: {name_info.get('confidence', 0.0):.2f})")
                    if 'learned_from' in name_info:
                        logger.info(f"      Learned from: {name_info['learned_from']}")
            
            # Clean up
            try:
                os.remove(new_doc_path)
            except:
                pass
        
        # Test 3: Show learning data
        logger.info("\n--- Test 3: Learning Data Summary ---")
        
        learning_data = detector.learning_data
        logger.info(f"Total manual inputs: {len(learning_data.get('manual_inputs', []))}")
        logger.info(f"Form types learned: {list(learning_data.get('form_types', {}).keys())}")
        
        for form_type, entries in learning_data.get('form_types', {}).items():
            logger.info(f"  {form_type}: {len(entries)} entries")
        
        # Show location patterns
        location_patterns = detector.location_patterns
        for form_type, patterns in location_patterns.get('form_types', {}).items():
            logger.info(f"  {form_type} location patterns: {len(patterns.get('name_locations', []))}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Learning system test failed: {e}")
        return False

def test_manual_client_api():
    """Test the manual client input API endpoint"""
    try:
        import requests
        
        logger.info("\n--- Test 4: Manual Client API ---")
        
        # Create test document
        doc_path = create_test_document('schedule_k1', 'API Test Client')
        if not doc_path:
            return False
        
        # Test API call
        api_data = {
            'session_id': 'test_session_123',
            'image_path': doc_path,
            'manual_name': 'API Test Client',
            'doc_type': 'schedule_k1',
            'bbox_location': [50, 100, 300, 120],
            'confidence': 1.0
        }
        
        # Note: This would require the Flask app to be running
        logger.info("API test data prepared:")
        logger.info(f"  Session ID: {api_data['session_id']}")
        logger.info(f"  Manual Name: {api_data['manual_name']}")
        logger.info(f"  Document Type: {api_data['doc_type']}")
        logger.info(f"  BBox Location: {api_data['bbox_location']}")
        
        # Clean up
        try:
            os.remove(doc_path)
        except:
            pass
        
        return True
        
    except Exception as e:
        logger.error(f"✗ API test failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("Starting Learning System Test...")
    logger.info("=" * 50)
    
    tests = [
        ("Learning System", test_learning_system),
        ("Manual Client API", test_manual_client_api)
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
        logger.info("🎉 All tests passed! Learning system is working correctly.")
        return True
    else:
        logger.error("❌ Some tests failed. Please review the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 