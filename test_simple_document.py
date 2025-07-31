#!/usr/bin/env python3
"""
Simple Document Test Script
Tests the enhanced name detection system with a simple mock document
"""

import os
import sys
import logging
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.enhanced_file_processor import EnhancedTaxDocumentProcessor
from config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_simple_document():
    """Test the enhanced name system with a simple mock document"""
    
    print("🧪 Testing Enhanced Name System with Simple Document")
    print("=" * 60)
    
    # Initialize the processor
    processor = EnhancedTaxDocumentProcessor(
        donut_model_path=Config.DONUT_MODEL_PATH,
        claude_api_key=Config.ANTHROPIC_API_KEY
    )
    
    # Create a simple test with mock data that simulates a document with actual names
    test_cases = [
        {
            'name': 'John Smith',
            'doc_type': 'K-1',
            'description': 'K-1 with John Smith',
            'mock_data': {
                'document_type': 'K-1',
                'client_name': 'John Smith',
                'person_name': 'John Smith',
                'partner_first_name': 'John',
                'partner_last_name': 'Smith',
                'tax_year': '2023',
                'confidence': 0.95
            }
        },
        {
            'name': 'Jane Doe',
            'doc_type': '1099-NEC',
            'description': '1099 with Jane Doe',
            'mock_data': {
                'document_type': '1099-NEC',
                'client_name': 'Jane Doe',
                'person_name': 'Jane Doe',
                'recipient_first_name': 'Jane',
                'recipient_last_name': 'Doe',
                'tax_year': '2023',
                'confidence': 0.95
            }
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case['description']}")
        print(f"   Expected Name: {test_case['name']}")
        print(f"   Document Type: {test_case['doc_type']}")
        
        try:
            # Test the enhanced name field mapping
            mapped_result = processor._enhanced_name_field_mapping(test_case['mock_data'], {})
            
            # Test entity recognition
            entity_info = processor.entity_recognizer.analyze_entity(mapped_result)
            
            # Test filename generation
            filename_info = processor.filename_generator.get_filename_preview(
                mapped_result, entity_info, f"test_{test_case['doc_type'].lower()}.pdf"
            )
            
            # Check results
            success = True
            issues = []
            
            # Check if entity info has correct names
            entity_first_name = entity_info.get('first_name', 'Unknown')
            entity_last_name = entity_info.get('last_name', 'Unknown')
            
            if entity_first_name == 'Unknown' or entity_last_name == 'Unknown':
                success = False
                issues.append("Entity info has 'Unknown' names instead of detected names")
            
            # Check if filename contains the detected name
            generated_filename = filename_info.get('filename', '')
            if test_case['name'].split()[0].lower() not in generated_filename.lower():
                success = False
                issues.append("Generated filename doesn't contain detected name")
            
            # Store results
            test_result = {
                'test_case': test_case,
                'success': success,
                'issues': issues,
                'mapped_result': mapped_result,
                'entity_info': entity_info,
                'filename_info': filename_info,
                'generated_filename': generated_filename
            }
            
            results.append(test_result)
            
            # Print results
            if success:
                print(f"   ✅ SUCCESS")
                print(f"   📄 Generated Filename: {generated_filename}")
                print(f"   👤 Entity: {entity_first_name} {entity_last_name}")
            else:
                print(f"   ❌ FAILED")
                for issue in issues:
                    print(f"      - {issue}")
                print(f"   📄 Generated Filename: {generated_filename}")
                print(f"   👤 Entity: {entity_first_name} {entity_last_name}")
            
        except Exception as e:
            print(f"   💥 ERROR: {e}")
            results.append({
                'test_case': test_case,
                'success': False,
                'issues': [f"Exception: {e}"],
                'error': str(e)
            })
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SIMPLE DOCUMENT TEST SUMMARY")
    print("=" * 60)
    
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    print(f"✅ Successful Tests: {len(successful_tests)}/{len(results)}")
    print(f"❌ Failed Tests: {len(failed_tests)}/{len(results)}")
    
    if successful_tests:
        print("\n✅ SUCCESSFUL TESTS:")
        for result in successful_tests:
            print(f"   - {result['test_case']['description']}")
            print(f"     Name: {result['test_case']['name']}")
            print(f"     Entity: {result['entity_info'].get('first_name')} {result['entity_info'].get('last_name')}")
            print(f"     Filename: {result['generated_filename']}")
    
    if failed_tests:
        print("\n❌ FAILED TESTS:")
        for result in failed_tests:
            print(f"   - {result['test_case']['description']}")
            for issue in result['issues']:
                print(f"     • {issue}")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    if len(successful_tests) == len(results):
        print("   ✅ All simple document tests passed! The enhanced name system is working correctly.")
        print("   📝 The system can properly handle documents with actual person names.")
    elif len(successful_tests) > len(failed_tests):
        print("   ⚠️  Most simple document tests passed, but some issues remain.")
        print("   📝 Review failed tests above for specific issues.")
    else:
        print("   🚨 Multiple simple document tests failed.")
        print("   🔧 The name system needs significant improvements for basic functionality.")
    
    return results

if __name__ == "__main__":
    test_simple_document() 