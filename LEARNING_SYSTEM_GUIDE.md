# Learning System Guide

## Overview

The DIXII Processing System now includes an advanced learning system that allows BERT and LayoutLM models to learn from manual client inputs. This system improves name detection accuracy over time by:

1. **Learning from manual inputs** - When users manually enter names, the system learns from these inputs
2. **Location-based detection** - Remembers where names appear on specific form types
3. **Adaptive detection** - Uses learned patterns for similar forms in the future

## How It Works

### 1. Manual Client Mode Learning

When a user manually enters a client name, the system:

- **Captures the input** - Records the manually entered name
- **Stores location data** - Saves where the name was found on the document
- **Learns form patterns** - Associates the name with the document type
- **Updates detection models** - Improves future detection for similar forms

### 2. Location-Based Detection

The system learns to recognize names in specific locations on different form types:

- **Schedule K-1 forms** - Partner names typically appear in specific locations
- **W-2 forms** - Employee names have consistent positioning
- **1099 forms** - Payee names follow predictable patterns
- **Custom forms** - Adapts to any form type through learning

### 3. Adaptive Improvement

As more manual inputs are processed, the system:

- **Builds confidence** - Higher accuracy for frequently seen patterns
- **Reduces false positives** - Learns to avoid common misidentifications
- **Improves speed** - Faster detection for familiar form types
- **Maintains accuracy** - Continues to use multiple detection methods

## API Integration

### Manual Client Input Endpoint

```http
POST /manual_client_input
Content-Type: application/json

{
    "session_id": "unique_session_id",
    "image_path": "/path/to/document.png",
    "manual_name": "John Smith",
    "doc_type": "schedule_k1",
    "bbox_location": [50, 100, 300, 120],
    "confidence": 1.0
}
```

### Response

```json
{
    "success": true,
    "message": "Learned from manual input: John Smith",
    "session_id": "unique_session_id"
}
```

## Usage Examples

### 1. Learning from Manual Input

```python
from models.enhanced_name_detector import EnhancedNameDetector

# Initialize detector
detector = EnhancedNameDetector()

# Learn from manual input
detector.learn_from_manual_input(
    image_path="document.png",
    manual_name="John Smith",
    doc_type="schedule_k1",
    bbox_location=[50, 100, 300, 120],
    confidence=1.0
)
```

### 2. Enhanced Detection

```python
# Detect names with learning system
results = detector.detect_names_in_document("new_document.png", "schedule_k1")

# Results now include location-based detection
print(f"Location-based names: {len(results['location_names'])}")
print(f"Combined names: {len(results['combined_names'])}")
print(f"Confidence: {results['confidence']}")
```

### 3. API Integration

```python
import requests

# Send manual input to API
response = requests.post('http://localhost:5000/manual_client_input', json={
    'session_id': 'session_123',
    'image_path': 'document.png',
    'manual_name': 'Jane Doe',
    'doc_type': 'w2',
    'bbox_location': [50, 100, 300, 120],
    'confidence': 1.0
})

print(response.json())
```

## Learning Data Storage

### File Structure

```
models/
├── name_learning_data.json      # Manual input learning data
├── location_patterns.json       # Location-based patterns
└── enhanced_name_detector.py    # Main detector with learning
```

### Learning Data Format

```json
{
    "manual_inputs": [
        {
            "timestamp": "2025-07-29T17:58:47.129",
            "image_path": "document.png",
            "manual_name": "John Smith",
            "doc_type": "schedule_k1",
            "bbox_location": [50, 100, 300, 120],
            "confidence": 1.0,
            "ocr_results": [...],
            "image_size": [800, 600]
        }
    ],
    "form_types": {
        "schedule_k1": [
            {
                "name": "John Smith",
                "bbox": [50, 100, 300, 120],
                "timestamp": "2025-07-29T17:58:47.129"
            }
        ]
    }
}
```

### Location Patterns Format

```json
{
    "form_types": {
        "schedule_k1": {
            "name_locations": [
                {
                    "name": "John Smith",
                    "bbox": [0.0625, 0.1667, 0.375, 0.2],
                    "timestamp": "2025-07-29T17:58:47.129"
                }
            ],
            "confidence_threshold": 0.7
        }
    }
}
```

## Benefits

### 1. Improved Accuracy

- **Reduced false positives** - Learns from user corrections
- **Higher confidence** - Builds trust in detection patterns
- **Better precision** - Location-based detection reduces errors

### 2. Adaptive Learning

- **Form-specific patterns** - Different learning for different form types
- **User-specific preferences** - Adapts to user's naming conventions
- **Continuous improvement** - Gets better with each manual input

### 3. Efficiency Gains

- **Faster processing** - Learned patterns speed up detection
- **Reduced manual work** - Fewer corrections needed over time
- **Better user experience** - More accurate initial detections

## Testing

### Run Learning System Test

```bash
python3 test_learning_system.py
```

### Expected Output

```
Starting Learning System Test...
==================================================

--- Test 1: Learning from Manual Input ---
✓ Learned: John Smith on schedule_k1
✓ Learned: Jane Doe on w2
✓ Learned: Robert Johnson on 1099

--- Test 2: Location-Based Detection ---
Detection Results:
  LayoutLM names: 1
  BERT NER names: 0
  Pattern names: 2
  Location names: 4
  Combined names: 5
  Confidence: 0.88
  Methods used: ['layoutlm', 'bert_ner', 'patterns', 'location_pattern']

--- Test 3: Learning Data Summary ---
Total manual inputs: 5
Form types learned: ['schedule_k1', 'w2', '1099']
  schedule_k1: 2 entries
  w2: 2 entries
  1099: 1 entries

==================================================
TEST SUMMARY
==================================================
Learning System: PASS
Manual Client API: PASS

Overall: 2/2 tests passed
🎉 All tests passed! Learning system is working correctly.
```

## Integration with Existing System

### 1. Automatic Integration

The learning system is automatically integrated into the existing name detection pipeline:

- **No code changes required** - Works with existing API endpoints
- **Backward compatible** - Doesn't affect current functionality
- **Progressive enhancement** - Improves over time without breaking changes

### 2. Enhanced Results

Detection results now include:

```python
{
    'layoutlm_names': [...],      # LayoutLM detections
    'bert_ner_names': [...],      # BERT NER detections
    'pattern_names': [...],       # Pattern-based detections
    'location_names': [...],      # NEW: Location-based detections
    'combined_names': [...],      # All combined with learning
    'confidence': 0.88,           # Improved confidence
    'detection_methods': ['layoutlm', 'bert_ner', 'patterns', 'location_pattern']
}
```

### 3. Session Management

Manual inputs are tracked per session:

```python
# Session includes manual inputs
session = {
    'results': [...],
    'manual_inputs': [
        {
            'name': 'John Smith',
            'doc_type': 'schedule_k1',
            'timestamp': '2025-07-29T17:58:47.129',
            'confidence': 1.0
        }
    ]
}
```

## Best Practices

### 1. Manual Input Quality

- **Accurate names** - Ensure manual inputs are correct
- **Consistent formatting** - Use consistent name formats
- **Proper document types** - Specify correct document types

### 2. Learning Data Management

- **Regular backups** - Backup learning data files
- **Periodic cleanup** - Remove old or incorrect patterns
- **Validation** - Verify learning data integrity

### 3. Performance Optimization

- **Limit pattern storage** - Keep only recent patterns (last 50)
- **Confidence thresholds** - Use appropriate confidence levels
- **Memory management** - Monitor learning data size

## Troubleshooting

### Common Issues

1. **Learning data not saving**
   - Check file permissions
   - Verify directory exists
   - Check disk space

2. **Location detection not working**
   - Verify bbox coordinates
   - Check form type matching
   - Validate overlap calculations

3. **API endpoint errors**
   - Check required fields
   - Verify session ID
   - Ensure image path exists

### Debug Commands

```bash
# Test learning system
python3 test_learning_system.py

# Check learning data
cat models/name_learning_data.json

# Check location patterns
cat models/location_patterns.json

# Test specific detection
python3 test_bert_layoutlm.py
```

## Future Enhancements

### Planned Features

1. **Advanced Learning Algorithms**
   - Machine learning model updates
   - Neural network fine-tuning
   - Transfer learning capabilities

2. **Enhanced Pattern Recognition**
   - Multi-page document support
   - Complex form layouts
   - Dynamic pattern adaptation

3. **User Interface Integration**
   - Learning progress indicators
   - Pattern visualization
   - Manual correction tools

### Performance Improvements

1. **Faster Learning**
   - Incremental model updates
   - Parallel processing
   - Cached pattern matching

2. **Better Accuracy**
   - Ensemble learning methods
   - Confidence calibration
   - Error analysis tools

## Conclusion

The learning system significantly enhances the DIXII Processing System's name detection capabilities by:

- **Learning from user inputs** - Improves accuracy over time
- **Location-based detection** - Reduces false positives
- **Adaptive improvement** - Gets better with each use
- **Seamless integration** - Works with existing workflows

This system transforms manual client mode from a simple fallback into a powerful learning opportunity that continuously improves the system's performance. 