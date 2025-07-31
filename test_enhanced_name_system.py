#!/usr/bin/env python3
"""
Enhanced Name System Test Script
Tests the improved name detection and filename generation system
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

def test_enhanced_name_system():
    """Test the enhanced name detection and filename generation system"""
    
    print("🧪 Testing Enhanced Name System")
    print("=" * 50)
    
    # Initialize the processor
    processor = EnhancedTaxDocumentProcessor(
        donut_model_path=Config.DONUT_MODEL_PATH,
        claude_api_key=Config.ANTHROPIC_API_KEY
    )
    
    # Test cases with different document types and names
    test_cases = [
        {
            'name': 'John Smith',
            'doc_type': 'K-1',
            'description': 'K-1 Partner Name Detection'
        },
        {
            'name': 'Jane Doe',
            'doc_type': '1099-NEC',
            'description': '1099 Recipient Name Detection'
        },
        {
            'name': 'Robert Johnson',
            'doc_type': 'W-2',
            'description': 'W-2 Employee Name Detection'
        },
        {
            'name': 'Mary Williams',
            'doc_type': '1040',
            'description': '1040 Taxpayer Name Detection'
        },
        {
            'name': 'David Brown',
            'doc_type': '1098',
            'description': '1098 Borrower Name Detection'
        }
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📋 Test {i}: {test_case['description']}")
        print(f"   Expected Name: {test_case['name']}")
        print(f"   Document Type: {test_case['doc_type']}")
        
        # Create a mock result with the test data
        mock_result = {
            'status': 'completed',
            'document_type': test_case['doc_type'],
            'client_name': test_case['name'],
            'person_name': test_case['name'],
            'detected_primary_name': test_case['name'],
            'detected_first_name': test_case['name'].split()[0],
            'detected_last_name': ' '.join(test_case['name'].split()[1:]),
            'enhanced_name_mapping_applied': True,
            'mapped_primary_name': test_case['name'],
            'mapped_first_name': test_case['name'].split()[0],
            'mapped_last_name': ' '.join(test_case['name'].split()[1:]),
            'tax_year': '2023',
            'confidence': 0.95
        }
        
        # Test the enhanced name field mapping
        try:
            # Apply field mapping
            mapped_result = processor._enhanced_name_field_mapping(mock_result, {})
            
            # Test entity recognition
            entity_info = processor.entity_recognizer.analyze_entity(mapped_result)
            
            # Test filename generation
            filename_info = processor.filename_generator.get_filename_preview(
                mapped_result, entity_info, f"test_{test_case['doc_type'].lower()}.pdf"
            )
            
            # Check results
            success = True
            issues = []
            
            # Check if name was properly mapped
            if not mapped_result.get('mapped_first_name') or not mapped_result.get('mapped_last_name'):
                success = False
                issues.append("Name not properly mapped to first/last name fields")
            
            # Check if entity info has correct names
            if entity_info.get('first_name') == 'Unknown' or entity_info.get('last_name') == 'Unknown':
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
                print(f"   👤 Entity: {entity_info.get('first_name')} {entity_info.get('last_name')}")
            else:
                print(f"   ❌ FAILED")
                for issue in issues:
                    print(f"      - {issue}")
                print(f"   📄 Generated Filename: {generated_filename}")
                print(f"   👤 Entity: {entity_info.get('first_name')} {entity_info.get('last_name')}")
            
        except Exception as e:
            print(f"   💥 ERROR: {e}")
            results.append({
                'test_case': test_case,
                'success': False,
                'issues': [f"Exception: {e}"],
                'error': str(e)
            })
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    print(f"✅ Successful Tests: {len(successful_tests)}/{len(results)}")
    print(f"❌ Failed Tests: {len(failed_tests)}/{len(results)}")
    
    if failed_tests:
        print("\n❌ FAILED TEST DETAILS:")
        for result in failed_tests:
            print(f"   - {result['test_case']['description']}")
            for issue in result['issues']:
                print(f"     • {issue}")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    if len(successful_tests) == len(results):
        print("   ✅ All tests passed! The enhanced name system is working correctly.")
    elif len(successful_tests) > len(failed_tests):
        print("   ⚠️  Most tests passed, but some issues remain. Review failed tests above.")
    else:
        print("   🚨 Multiple tests failed. The name system needs significant improvements.")
    
    return results

if __name__ == "__main__":
    test_enhanced_name_system() 