# DIXII Processing System Troubleshooting Guide

## Issues Identified and Fixed

### 1. LayoutLM Name Detection Error: `'bbox'`

**Problem**: The LayoutLM name detection was failing because OCR results didn't contain the expected bounding box data structure.

**Root Cause**: 
- OCR results were not properly validated before processing
- Missing error handling for malformed bbox data
- No validation of OCR result structure

**Fix Applied**:
- Added comprehensive validation of OCR results structure
- Added proper error handling for bbox normalization
- Added logging for debugging OCR issues
- Added fallback handling for malformed data

**Code Location**: `models/enhanced_name_detector.py` lines 185-267

### 2. Document Preprocessing Error: `argument of type 'NoneType' is not iterable`

**Problem**: Document preprocessing was failing when encountering None values in data structures.

**Root Cause**:
- Missing validation of input parameters
- No handling for None document types
- Insufficient error handling in preprocessing pipeline

**Fix Applied**:
- Added input validation for image paths and document types
- Added None value handling for document types
- Added comprehensive error handling in preprocessing
- Added validation of preprocessing results

**Code Location**: `utils/document_type_aware_preprocessor.py` lines 244-290

### 3. Results Not Showing in Dashboard

**Problem**: Processing completes but results aren't displayed in the dashboard.

**Root Cause**:
- Results not properly stored in session
- Missing validation of result data structures
- Insufficient error handling in result processing

**Fix Applied**:
- Added proper result validation and storage
- Added comprehensive error handling for batch processing
- Added validation of result data structures
- Added fallback error states for failed processing

**Code Location**: `run.py` lines 133-280

## Troubleshooting Steps

### For LayoutLM Errors:

1. **Check OCR Installation**:
   ```bash
   # Ensure tesseract is properly installed
   tesseract --version
   ```

2. **Verify Image Quality**:
   - Ensure images are clear and readable
   - Check if images are corrupted
   - Verify image format is supported

3. **Check Model Files**:
   ```bash
   # Verify model files exist
   ls -la models/
   ```

### For Document Preprocessing Errors:

1. **Check File Permissions**:
   ```bash
   # Ensure upload directory is writable
   chmod 755 uploads/
   chmod 755 processed/
   ```

2. **Verify Configuration**:
   ```bash
   # Check config values
   python -c "from config import Config; print(Config.ENABLE_SPEED_OPTIMIZATIONS)"
   ```

3. **Check Dependencies**:
   ```bash
   # Install required packages
   pip install -r requirements.txt
   ```

### For Results Display Issues:

1. **Check Session Storage**:
   ```bash
   # Monitor session data
   curl http://localhost:5000/api/debug-sessions
   ```

2. **Verify File Processing**:
   ```bash
   # Check processed files
   ls -la processed/
   ```

3. **Check Logs**:
   ```bash
   # Monitor application logs
   tail -f app.log
   ```

## Debugging Commands

### 1. Test Name Detection:
```python
from models.enhanced_name_detector import EnhancedNameDetector

detector = EnhancedNameDetector()
results = detector.detect_names_in_document("test_image.jpg", "W-2")
print(results)
```

### 2. Test Document Preprocessing:
```python
from utils.document_type_aware_preprocessor import DocumentTypeAwarePreprocessor

preprocessor = DocumentTypeAwarePreprocessor()
results = preprocessor.preprocess_document("test_image.jpg", "W-2", 0.8)
print(results)
```

### 3. Test File Processing:
```python
from utils.enhanced_file_processor import EnhancedTaxDocumentProcessor

processor = EnhancedTaxDocumentProcessor("model_path", "api_key")
result = processor.process_document("test_file.pdf", "test.pdf")
print(result)
```

## Common Error Messages and Solutions

### 1. `'bbox'` Error
**Message**: `Error in LayoutLM name detection: 'bbox'`
**Solution**: 
- Check if tesseract is properly installed
- Verify image quality and format
- Check OCR results structure

### 2. `NoneType is not iterable`
**Message**: `argument of type 'NoneType' is not iterable`
**Solution**:
- Check input validation
- Verify data structures
- Add proper error handling

### 3. Results Not Displaying
**Message**: No results shown in dashboard
**Solution**:
- Check session storage
- Verify result validation
- Monitor processing logs

## Performance Optimization

### 1. Speed Optimizations:
- Enable/disable speed optimizations in config
- Adjust confidence thresholds
- Use batch processing for multiple files

### 2. Memory Management:
- Clean up temporary files
- Monitor memory usage
- Use efficient data structures

### 3. Error Recovery:
- Implement retry mechanisms
- Add fallback processing
- Improve error reporting

## Monitoring and Logging

### 1. Enable Debug Logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. Monitor Processing:
```bash
# Watch processing logs
tail -f logs/processing.log
```

### 3. Check System Resources:
```bash
# Monitor CPU and memory
htop
```

## Prevention Measures

### 1. Input Validation:
- Always validate input parameters
- Check file existence and permissions
- Verify data structure integrity

### 2. Error Handling:
- Add comprehensive try-catch blocks
- Implement graceful degradation
- Provide meaningful error messages

### 3. Testing:
- Test with various file formats
- Test with different document types
- Test error conditions

## Support and Maintenance

### 1. Regular Maintenance:
- Clean up old sessions and files
- Monitor system performance
- Update dependencies regularly

### 2. Backup and Recovery:
- Backup configuration files
- Backup processed data
- Implement recovery procedures

### 3. Documentation:
- Keep troubleshooting guide updated
- Document configuration changes
- Maintain change logs

## Quick Fix Checklist

- [ ] Verify tesseract installation
- [ ] Check file permissions
- [ ] Validate configuration
- [ ] Test with sample files
- [ ] Monitor error logs
- [ ] Verify model files
- [ ] Check API keys
- [ ] Test network connectivity
- [ ] Validate input data
- [ ] Check output directories

## Emergency Procedures

### 1. System Reset:
```bash
# Clear all sessions and temporary files
rm -rf uploads/*
rm -rf processed/*
python -c "import os; os.system('rm -rf /tmp/dixii_*')"
```

### 2. Restart Services:
```bash
# Restart the application
pkill -f run.py
python run.py
```

### 3. Rollback Changes:
```bash
# Revert to previous version
git checkout HEAD~1
pip install -r requirements.txt
```

This troubleshooting guide should help resolve the issues you're experiencing with the name detection software and processing system. 