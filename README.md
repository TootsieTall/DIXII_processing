# 📄 DIXII - AI Tax Document Processor

An intelligent AI-powered application that automatically classifies, extracts client information, and organizes tax documents using cutting-edge machine learning models.

## 🚀 Quick Start (Choose Your Path)

**Complete beginner?** Start here:
- 🟢 **[README_FOR_BEGINNERS.md](README_FOR_BEGINNERS.md)** - Absolute simplest guide (3 steps!)

**New to coding?** Use our detailed guides:
- 📘 **[EASY_SETUP.md](EASY_SETUP.md)** - Step-by-step with troubleshooting
- 📗 **[ONE_PAGE_SETUP.md](ONE_PAGE_SETUP.md)** - Quick 3-minute setup

**Already comfortable with Python?** Just run:
```bash
pip install -r requirements.txt && python run.py
```
Then go to http://localhost:8080

## ✨ Features

### 🤖 **AI-Powered Processing**
- **Donut IRS Model**: Classifies 22+ tax document types (1040, W-2, 1099, K-1, etc.)
- **Claude API Integration**: Extracts client names, tax years, and document details
- **Enhanced Entity Recognition**: Automatically identifies individuals, businesses, trusts, and partnerships
- **Form-Specific Processing**: Specialized extraction for different tax forms

### 📁 **Smart Organization**
- **Intelligent File Naming**: `FirstName L. DocumentType Year.ext`
- **Client Folder Creation**: Organizes documents by client automatically
- **Case-Insensitive Names**: `"John Smith"`, `"john smith"`, `"JOHN SMITH"` → same folder
- **Business Entity Support**: Handles LLCs, Corporations, Partnerships, Trusts

### 🎯 **Dual Processing Modes**
- **Auto Mode**: AI extracts all information automatically
- **Manual Mode**: User specifies client name, AI handles document type and year

### 🖥️ **Modern Web Interface**
- **Glassmorphism Design**: Beautiful modern interface with blur effects
- **Real-time Progress**: Live status updates and progress tracking
- **File Explorer**: Browse, rename, and organize processed files
- **Dark Mode Support**: Automatic system theme detection
- **Responsive Design**: Works on desktop and mobile devices

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Claude API key from Anthropic
- 4GB+ RAM (for AI models)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/DIXII_processing.git
   cd DIXII_processing
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Download the AI model**
   ```bash
   python download_model.py
   ```

4. **Set up API key**
   ```bash
   echo "ANTHROPIC_API_KEY=your_api_key_here" > .env
   ```

5. **Run the application**
   ```bash
   python run.py
   ```

6. **Open your browser**
   Navigate to `http://localhost:8080`

## 📖 Usage Guide

### 1. Upload Documents
- Choose between **Auto Mode** (AI extracts everything) or **Manual Mode** (specify client)
- Select Enhanced Recognition or Basic Detection
- Choose Smart Templates or Simple Format
- Drag & drop or click to select files
- Supports: PDF, PNG, JPG, JPEG, TIFF, BMP (max 16MB each)

### 2. Monitor Processing
- Watch real-time progress with modern animated indicators
- See individual file status: Waiting → Processing → Completed
- View confidence scores and processing details

### 3. Review Results
- View comprehensive processing statistics
- Browse organized files with the built-in file explorer
- Access advanced features like document preview and bulk renaming

## 🏗️ Project Structure

```
DIXII_processing/
├── 📄 run.py                       # Main application runner

├── 📄 config.py                    # Configuration settings
├── 📄 requirements.txt             # Python dependencies
├── 📁 models/                      # AI model implementations
│   ├── enhanced_claude_ocr.py      # Enhanced Claude OCR
│   └── donut_classifier.py         # Donut document classifier
├── 📁 utils/                       # Processing utilities
│   ├── enhanced_file_processor.py  # Main processing logic
│   ├── entity_recognizer.py        # Entity recognition
│   └── filename_generator.py       # Smart filename generation
├── 📁 templates/                   # Web interface
│   └── modern_enhanced_index.html  # Modern UI template
├── 📁 donut-irs-tax-docs-classifier/ # Pre-trained model files
├── 📁 uploads/                     # Temporary upload storage
└── 📁 processed/                   # Organized output files
```

## 🔧 Configuration

### Environment Variables (.env)
```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

### Settings Panel
- Access via the ⚙️ button in the web interface
- Configure API key without editing files
- Secure password-style input with show/hide toggle

## 📊 Supported Document Types

- **Form 1040** (Individual Income Tax Return)
- **Form W-2** (Wage and Tax Statement)  
- **Form 1099** (All variants: NEC, MISC, INT, DIV, R, etc.)
- **Schedule K-1** (Partnership, S-Corp, Trust distributions)
- **Form 1098** (Mortgage Interest, Education expenses)
- **Form W-9** (Request for Taxpayer ID)
- **State Tax Forms**
- **Business Returns** (1120, 1120S, 1065, etc.)

## 🛠️ Troubleshooting

### Common Issues:

1. **"Enhanced processor not initialized"**
   - Check your `.env` file has the correct Claude API key
   - Use the Settings panel to configure your API key

2. **PDF conversion errors**
   - Install system dependencies: `brew install poppler` (macOS)
   - Check PDF files are not corrupted

3. **Poor recognition accuracy**
   - Use high-quality scans (200+ DPI)
   - Ensure documents are clearly readable
   - Try manual mode for known clients

4. **Claude API errors**
   - Verify your API key is valid and has credits
   - Check internet connection

## 💡 Tips for Best Results

- **High-Quality Scans**: Use 200+ DPI for best OCR results
- **Batch Processing**: Process multiple clients' documents together
- **Document Quality**: Ensure text is clear and readable
- **File Names**: Original filenames don't matter - they'll be intelligently renamed

## 🔒 Security & Privacy

- **Local Processing**: Documents processed locally on your machine
- **API Usage**: Claude API used only for OCR/classification
- **No Permanent Storage**: No documents stored by external services
- **Automatic Cleanup**: Temporary files cleaned after processing

## 🆘 Support

For issues or questions:
1. Check this README for common solutions
2. Review the application logs for error details
3. Verify your API key configuration
4. Ensure all system dependencies are installed

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
