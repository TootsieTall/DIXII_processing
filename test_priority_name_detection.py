#!/usr/bin/env python3
"""
Test script to verify that enhanced name detection is the FIRST LINE for client naming
and entity naming, with Claude as fallback.
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent))

from utils.enhanced_file_processor import EnhancedTaxDocumentProcessor
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_priority_name_detection():
    """Test that enhanced name detection is prioritized over Claude extraction"""
    
    # Initialize the processor
    processor = EnhancedTaxDocumentProcessor(
        donut_model_path=Config.DONUT_MODEL_PATH,
        claude_api_key=Config.ANTHROPIC_API_KEY
    )
    
    print("🧪 Testing Priority Name Detection System")
    print("=" * 50)
    
    # Test with a sample document from uploads folder
    uploads_dir = Path("uploads")
    if not uploads_dir.exists():
        print("❌ Uploads directory not found. Please add some test documents to the uploads folder.")
        return
    
    # Find a test document
    test_files = list(uploads_dir.glob("*.pdf")) + list(uploads_dir.glob("*.jpg")) + list(uploads_dir.glob("*.png"))
    
    if not test_files:
        print("❌ No test files found in uploads directory.")
        return
    
    test_file = test_files[0]
    print(f"📄 Testing with: {test_file.name}")
    
    # Process the document
    result = processor.process_document(
        file_path=str(test_file),
        original_filename=test_file.name
    )
    
    print("\n📊 Processing Results:")
    print("-" * 30)
    
    if result['status'] == 'success':
        print(f"✅ Status: {result['status']}")
        print(f"📋 Document Type: {result.get('document_type', 'Unknown')}")
        print(f"👤 Client Name: {result.get('client_name', 'Unknown')}")
        print(f"👤 Person Name: {result.get('person_name', 'Unknown')}")
        print(f"📅 Tax Year: {result.get('tax_year', 'Unknown')}")
        print(f"🎯 Confidence: {result.get('confidence', 0.0)}")
        
        # Check name detection results
        name_detection = result.get('name_detection_results', {})
        if name_detection:
            print(f"\n🔍 Name Detection Results:")
            print(f"   Confidence: {name_detection.get('confidence', 0.0)}")
            print(f"   Methods Used: {', '.join(name_detection.get('detection_methods', []))}")
            print(f"   Names Found: {len(name_detection.get('combined_names', []))}")
            
            # Show detected names
            combined_names = name_detection.get('combined_names', [])
            if combined_names:
                print(f"   Detected Names:")
                for i, name_info in enumerate(combined_names[:5], 1):  # Show first 5
                    print(f"     {i}. {name_info.get('name', 'Unknown')} (confidence: {name_info.get('confidence', 0.0)})")
        
        # Check if enhanced detection was prioritized
        extracted_details = result.get('extracted_details', {})
        if 'enhanced_name_detection' in extracted_details:
            print(f"\n🎯 Enhanced Detection Priority:")
            print(f"   ✅ Enhanced detection was used as first line")
            
            if 'claude_override_notes' in extracted_details:
                print(f"   📝 Override: {extracted_details['claude_override_notes']}")
            
            if 'name_detection_fallback' in extracted_details:
                print(f"   🔄 Fallback: Used {extracted_details['name_detection_fallback']} as fallback")
        
        # Show processing notes
        processing_notes = result.get('processing_notes', [])
        if processing_notes:
            print(f"\n📝 Processing Notes:")
            for note in processing_notes:
                print(f"   • {note}")
        
        # Show entity info
        entity_info = result.get('entity_info', {})
        if entity_info:
            print(f"\n🏢 Entity Information:")
            print(f"   Entity Type: {entity_info.get('entity_type', 'Unknown')}")
            print(f"   Display Name: {entity_info.get('display_name', 'Unknown')}")
            print(f"   Is Joint Return: {entity_info.get('is_joint', False)}")
        
    else:
        print(f"❌ Status: {result['status']}")
        print(f"❌ Error: {result.get('error', 'Unknown error')}")
    
    print("\n" + "=" * 50)
    print("✅ Priority Name Detection Test Complete")
    
    return result

def test_multiple_documents():
    """Test priority name detection with multiple documents"""
    
    processor = EnhancedTaxDocumentProcessor(
        donut_model_path=Config.DONUT_MODEL_PATH,
        claude_api_key=Config.ANTHROPIC_API_KEY
    )
    
    print("\n🧪 Testing Multiple Documents")
    print("=" * 50)
    
    uploads_dir = Path("uploads")
    if not uploads_dir.exists():
        print("❌ Uploads directory not found.")
        return
    
    test_files = list(uploads_dir.glob("*.pdf")) + list(uploads_dir.glob("*.jpg")) + list(uploads_dir.glob("*.png"))
    
    if len(test_files) < 2:
        print("⚠️  Need at least 2 test files for multiple document testing.")
        return
    
    results = []
    
    for i, test_file in enumerate(test_files[:3], 1):  # Test first 3 files
        print(f"\n📄 Testing Document {i}: {test_file.name}")
        
        try:
            result = processor.process_document(
                file_path=str(test_file),
                original_filename=test_file.name
            )
            
            if result['status'] == 'success':
                client_name = result.get('client_name', 'Unknown')
                name_detection = result.get('name_detection_results', {})
                confidence = name_detection.get('confidence', 0.0)
                
                print(f"   ✅ Client: {client_name}")
                print(f"   🎯 Confidence: {confidence}")
                print(f"   🔍 Methods: {', '.join(name_detection.get('detection_methods', []))}")
                
                results.append({
                    'file': test_file.name,
                    'client_name': client_name,
                    'confidence': confidence,
                    'methods': name_detection.get('detection_methods', [])
                })
            else:
                print(f"   ❌ Failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   Documents Processed: {len(results)}")
    successful = [r for r in results if r['client_name'] != 'Unknown']
    print(f"   Successful Name Detection: {len(successful)}")
    
    if successful:
        avg_confidence = sum(r['confidence'] for r in successful) / len(successful)
        print(f"   Average Confidence: {avg_confidence:.2f}")
        
        # Count method usage
        method_counts = {}
        for r in successful:
            for method in r['methods']:
                method_counts[method] = method_counts.get(method, 0) + 1
        
        print(f"   Method Usage:")
        for method, count in method_counts.items():
            print(f"     {method}: {count}")

if __name__ == "__main__":
    print("🚀 Starting Priority Name Detection Tests")
    print("=" * 60)
    
    # Test single document
    test_priority_name_detection()
    
    # Test multiple documents
    test_multiple_documents()
    
    print("\n🎉 All tests completed!") 