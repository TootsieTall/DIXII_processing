#!/usr/bin/env python3
"""
Test script for enhanced name detection using multiple specialized models.
This demonstrates how to integrate the enhanced name detector into your existing system.
"""

import os
import sys
import logging
from models.enhanced_name_detector import EnhancedNameDetector

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_name_detection(image_path: str, doc_type: str = None):
    """
    Test the enhanced name detection on a document image
    
    Args:
        image_path: Path to the document image
        doc_type: Document type (optional, for targeted detection)
    """
    try:
        # Initialize the enhanced name detector
        logger.info("Initializing Enhanced Name Detector...")
        name_detector = EnhancedNameDetector()
        
        # Detect names in the document
        logger.info(f"Detecting names in: {image_path}")
        results = name_detector.detect_names_in_document(image_path, doc_type)
        
        # Print results
        print("\n" + "="*60)
        print("ENHANCED NAME DETECTION RESULTS")
        print("="*60)
        
        print(f"\nDocument: {image_path}")
        print(f"Document Type: {doc_type or 'Unknown'}")
        print(f"Detection Methods Used: {', '.join(results['detection_methods'])}")
        print(f"Overall Confidence: {results['confidence']:.2f}")
        
        print(f"\nCombined Results ({len(results['combined_names'])} names found):")
        for i, name_info in enumerate(results['combined_names'], 1):
            print(f"  {i}. {name_info['name']} (confidence: {name_info['confidence']:.2f}, method: {name_info['method']})")
        
        # Show individual method results
        if results['layoutlm_names']:
            print(f"\nLayoutLM Results ({len(results['layoutlm_names'])} names):")
            for name_info in results['layoutlm_names']:
                print(f"  - {name_info['name']} (confidence: {name_info['confidence']:.2f})")
        
        if results['bert_ner_names']:
            print(f"\nBERT NER Results ({len(results['bert_ner_names'])} names):")
            for name_info in results['bert_ner_names']:
                print(f"  - {name_info['name']} (confidence: {name_info['confidence']:.2f})")
        
        if results['pattern_names']:
            print(f"\nPattern Results ({len(results['pattern_names'])} names):")
            for name_info in results['pattern_names']:
                print(f"  - {name_info['name']} (confidence: {name_info['confidence']:.2f})")
        
        # Get primary client name
        primary_name = name_detector.get_primary_client_name(results)
        if primary_name:
            print(f"\nPrimary Client Name: {primary_name}")
        
        # Get all detected names
        all_names = name_detector.get_all_detected_names(results)
        if all_names:
            print(f"\nAll Detected Names: {', '.join(all_names)}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in name detection test: {e}")
        return None

def integrate_with_existing_system():
    """
    Example of how to integrate the enhanced name detector with your existing system
    """
    print("\n" + "="*60)
    print("INTEGRATION EXAMPLE")
    print("="*60)
    
    # This is how you would integrate it into your existing enhanced_file_processor.py
    integration_code = '''
# In your enhanced_file_processor.py, add this import:
from models.enhanced_name_detector import EnhancedNameDetector

# In the __init__ method, add:
self.name_detector = EnhancedNameDetector()

# In your process_document method, after document classification:
def process_document(self, file_path: str, original_filename: str, manual_client_info: Optional[Dict] = None) -> Dict:
    # ... existing code ...
    
    # After document type classification, add enhanced name detection:
    if donut_result and donut_result.get('document_type'):
        doc_type = donut_result['document_type']
        name_detection_results = self.name_detector.detect_names_in_document(image_path, doc_type)
        
        # Use the detected names to improve entity recognition
        primary_name = self.name_detector.get_primary_client_name(name_detection_results)
        if primary_name:
            # Update extracted info with detected names
            extracted_info['detected_names'] = name_detection_results
            extracted_info['primary_client_name'] = primary_name
            
            # If we have high confidence names, use them
            if name_detection_results['confidence'] > 0.7:
                # Parse the name into first/last
                name_parts = primary_name.split()
                if len(name_parts) >= 2:
                    extracted_info['detected_first_name'] = name_parts[0]
                    extracted_info['detected_last_name'] = ' '.join(name_parts[1:])
    
    # ... rest of existing code ...
'''
    
    print(integration_code)

if __name__ == "__main__":
    # Example usage
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        doc_type = sys.argv[2] if len(sys.argv) > 2 else None
        
        if os.path.exists(image_path):
            test_name_detection(image_path, doc_type)
        else:
            print(f"Error: Image file not found: {image_path}")
    else:
        print("Usage: python test_enhanced_name_detection.py <image_path> [document_type]")
        print("\nExample:")
        print("  python test_enhanced_name_detection.py sample_k1.pdf 'k1_recipient'")
        print("  python test_enhanced_name_detection.py sample_w2.jpg 'w2_employee'")
        
        # Show integration example
        integrate_with_existing_system() 