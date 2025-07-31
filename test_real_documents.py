#!/usr/bin/env python3
"""
Real Document Test Script
Tests the enhanced name detection system with real processed documents
"""

import os
import sys
import logging
from pathlib import Path
import json

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.enhanced_file_processor import EnhancedTaxDocumentProcessor
from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def find_test_documents():
    """Find documents in the processed directory for testing"""
    processed_dir = Path(Config.PROCESSED_FOLDER)
    test_documents = []
    
    # Look for PDF files in processed directories
    for folder in processed_dir.iterdir():
        if folder.is_dir() and not folder.name.startswith('.'):
            for file in folder.rglob('*.pdf'):
                test_documents.append({
                    'path': str(file),
                    'folder': folder.name,
                    'filename': file.name
                })
    
    return test_documents

def test_real_documents():
    """Test the enhanced name system with real documents"""
    
    print("🧪 Testing Enhanced Name System with Real Documents")
    print("=" * 60)
    
    # Initialize the processor
    processor = EnhancedTaxDocumentProcessor(
        donut_model_path=Config.DONUT_MODEL_PATH,
        claude_api_key=Config.ANTHROPIC_API_KEY
    )
    
    # Find test documents
    test_documents = find_test_documents()
    
    if not test_documents:
        print("❌ No test documents found in processed directory")
        return
    
    print(f"📁 Found {len(test_documents)} test documents")
    print("=" * 60)
    
    results = []
    
    # Test first 3 documents to avoid excessive API calls
    for i, doc in enumerate(test_documents[:3], 1):
        print(f"\n📋 Test {i}: {doc['filename']}")
        print(f"   📁 Folder: {doc['folder']}")
        print(f"   📄 Path: {doc['path']}")
        
        try:
            # Process the document
            result = processor.process_document(
                file_path=doc['path'],
                original_filename=doc['filename']
            )
            
            # Analyze results
            success = True
            issues = []
            
            # Check if processing was successful
            if result.get('status') != 'completed':
                success = False
                issues.append(f"Processing failed: {result.get('error', 'Unknown error')}")
            
            # Check name detection
            client_name = result.get('client_name', 'Unknown')
            person_name = result.get('person_name', 'Unknown')
            
            if client_name == 'Unknown' and person_name == 'Unknown':
                success = False
                issues.append("No names detected")
            
            # Check entity info
            entity_info = result.get('entity_info', {})
            entity_first_name = entity_info.get('first_name', 'Unknown')
            entity_last_name = entity_info.get('last_name', 'Unknown')
            
            if entity_first_name == 'Unknown' or entity_last_name == 'Unknown':
                success = False
                issues.append("Entity info has 'Unknown' names")
            
            # Check filename generation
            new_filename = result.get('new_filename')
            if not new_filename:
                success = False
                issues.append("No filename generated")
            
            # Check if filename contains detected name
            if client_name != 'Unknown' and client_name.split()[0].lower() not in new_filename.lower():
                success = False
                issues.append("Generated filename doesn't contain detected name")
            
            # Store results
            test_result = {
                'document': doc,
                'success': success,
                'issues': issues,
                'result': result,
                'client_name': client_name,
                'person_name': person_name,
                'entity_info': entity_info,
                'new_filename': new_filename
            }
            
            results.append(test_result)
            
            # Print results
            if success:
                print(f"   ✅ SUCCESS")
                print(f"   👤 Client Name: {client_name}")
                print(f"   👤 Person Name: {person_name}")
                print(f"   👤 Entity: {entity_first_name} {entity_last_name}")
                print(f"   📄 New Filename: {new_filename}")
                print(f"   📄 Document Type: {result.get('document_type', 'Unknown')}")
                print(f"   📊 Confidence: {result.get('confidence', 0.0):.2f}")
            else:
                print(f"   ❌ FAILED")
                for issue in issues:
                    print(f"      - {issue}")
                print(f"   👤 Client Name: {client_name}")
                print(f"   👤 Person Name: {person_name}")
                print(f"   👤 Entity: {entity_first_name} {entity_last_name}")
                print(f"   📄 New Filename: {new_filename}")
            
        except Exception as e:
            print(f"   💥 ERROR: {e}")
            results.append({
                'document': doc,
                'success': False,
                'issues': [f"Exception: {e}"],
                'error': str(e)
            })
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 REAL DOCUMENT TEST SUMMARY")
    print("=" * 60)
    
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    print(f"✅ Successful Tests: {len(successful_tests)}/{len(results)}")
    print(f"❌ Failed Tests: {len(failed_tests)}/{len(results)}")
    
    if successful_tests:
        print("\n✅ SUCCESSFUL DOCUMENTS:")
        for result in successful_tests:
            print(f"   - {result['document']['filename']}")
            print(f"     Client: {result['client_name']}")
            print(f"     Entity: {result['entity_info'].get('first_name')} {result['entity_info'].get('last_name')}")
            print(f"     Filename: {result['new_filename']}")
    
    if failed_tests:
        print("\n❌ FAILED DOCUMENTS:")
        for result in failed_tests:
            print(f"   - {result['document']['filename']}")
            for issue in result['issues']:
                print(f"     • {issue}")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    if len(successful_tests) == len(results):
        print("   ✅ All real document tests passed! The enhanced name system is working perfectly.")
    elif len(successful_tests) > len(failed_tests):
        print("   ⚠️  Most real document tests passed, but some issues remain.")
        print("   📝 Review failed tests above for specific issues.")
    else:
        print("   🚨 Multiple real document tests failed.")
        print("   🔧 The name system needs further improvements for real-world documents.")
    
    return results

if __name__ == "__main__":
    test_real_documents() 