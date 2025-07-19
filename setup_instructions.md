# Tax Document Sorter - Setup Instructions

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up Claude API Key
Create a `.env` file in the project root with your Claude API key:
```
ANTHROPIC_API_KEY=your_claude_api_key_here
```

To get a Claude API key:
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create a new API key
5. Copy the key to your `.env` file

### 3. Install System Dependencies

#### For PDF Processing (pdf2image):
- **macOS**: `brew install poppler`
- **Ubuntu/Debian**: `sudo apt-get install poppler-utils`
- **Windows**: Download and install poppler, add to PATH

#### For OCR (optional, if needed):
- **macOS**: `brew install tesseract`
- **Ubuntu/Debian**: `sudo apt-get install tesseract-ocr`

### 4. Run the Application
```bash
python app.py
```

The application will start on `http://localhost:5000`

## 📁 How It Works

1. **Upload**: Drag and drop or select tax documents (PDF, PNG, JPG, etc.)
2. **Processing**: The system will:
   - Use Donut model to classify document types
   - Use Claude API to extract client names and tax years
   - Rename files in format: `FirstName_LastName_DocumentType_Year.ext`
   - Organize files into client folders
3. **Results**: View processing statistics and download organized files

## 🔧 Configuration

Edit `config.py` to customize:
- File size limits
- Supported file formats
- Processing parameters
- Folder locations

## 📊 Document Types Supported by Donut Model

- Form 1040 (Individual Income Tax Return)
- Form W-2 (Wage and Tax Statement)
- Various 1040 Schedules (A, B, C, D, E, SE, etc.)
- Form 1040-NR (Nonresident Alien Return)
- Form 8949, 8959, 8960, 8995
- Form 1125-A
- Tax letters and miscellaneous documents

## 🛠️ Troubleshooting

### Common Issues:

1. **"Document processor not initialized"**
   - Check your `.env` file has the correct Claude API key
   - Ensure the donut model is in the correct path

2. **PDF conversion errors**
   - Install poppler as described above
   - Check PDF files are not corrupted

3. **Out of memory errors**
   - Reduce batch size
   - Process fewer files at once
   - Use CPU instead of GPU for smaller files

4. **Claude API errors**
   - Check your API key is valid
   - Ensure you have available credits
   - Check internet connection

### File Structure:
```
tax-document-sorter/
├── app.py                    # Main Flask application
├── config.py                 # Configuration settings
├── requirements.txt          # Python dependencies
├── models/                   # AI model classes
│   ├── donut_classifier.py   # Donut model wrapper
│   └── claude_ocr.py         # Claude API wrapper
├── utils/                    # Utility functions
│   └── file_processor.py     # Main processing logic
├── templates/                # Web interface
│   └── index.html           # Main webpage
├── donut-irs-tax-docs-classifier/  # Donut model files
├── uploads/                  # Temporary upload folder
└── processed/               # Organized output files
    └── [Client_Name]/       # Client folders
```

## 💡 Tips

- **Best Results**: Use high-quality scans/photos of documents
- **File Names**: Original filenames don't matter - they'll be renamed
- **Batch Processing**: Process multiple clients' documents at once
- **Error Handling**: Files that can't be processed are flagged for manual review

## 🔒 Security Notes

- Files are processed locally on your machine
- Claude API is used only for OCR/classification
- No documents are permanently stored by external services
- Temporary upload files are cleaned up after processing

## 🆘 Support

If you encounter issues:
1. Check the console output for error messages
2. Verify your `.env` configuration
3. Ensure all dependencies are installed
4. Check file permissions for upload/processed folders 