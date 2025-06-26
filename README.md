# 📄 Tax Document Sorter

An intelligent AI-powered application that automatically classifies, extracts client information, and organizes tax documents using cutting-edge machine learning models.

## ✨ Features

### 🤖 **AI-Powered Processing**
- **Donut IRS Model**: Classifies 22+ tax document types (W-9, 1040, W-2, etc.)
- **Claude API Integration**: Extracts client names, tax years, and provides fallback classification
- **Hybrid AI Approach**: Combines specialized models for maximum accuracy

### 📁 **Smart Organization**
- **Automatic File Naming**: `FirstName L. DocumentType Year.ext`
- **Client Folder Creation**: Organizes documents by client automatically
- **Duplicate Handling**: Intelligent file management and conflict resolution

### 🎯 **Dual Processing Modes**
- **Auto Mode**: AI extracts all information automatically
- **Manual Mode**: User specifies client name, AI handles document type and year

### 🖥️ **Modern Web Interface**
- **3-Tab Workflow**: Upload → Processing → Results
- **Real-time Progress**: Live status updates and progress tracking
- **File Explorer**: Browse, rename, and organize processed files
- **Responsive Design**: Works on desktop and mobile devices

### 🔧 **Advanced Features**
- **Settings Panel**: Easy API key management
- **List/Grid Views**: Multiple viewing options for file explorer
- **Drag & Drop**: Intuitive file organization
- **macOS Finder-style**: Familiar dropdown navigation

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
   python3 download_model.py
   ```

4. **Set up API key**
   ```bash
   echo "ANTHROPIC_API_KEY=your_api_key_here" > .env
   ```

5. **Run the application**
   ```bash
   python3 run.py
   ```

6. **Open your browser**
   Navigate to `http://localhost:8080`

## 📖 Usage Guide

### 1. Upload Documents
- Choose between **Auto Mode** (AI extracts everything) or **Manual Mode** (specify client)
- Drag & drop or click to select files
- Supports: PDF, PNG, JPG, JPEG, TIFF, BMP (max 16MB each)

### 2. Monitor Processing
- Watch real-time progress in the Processing tab
- See individual file status: Waiting → Processing → Completed
- Progress bar advances only when files are actually completed

### 3. Review Results
- View processing statistics and success rates
- Browse organized files with the built-in file explorer
- Access files through List View (dropdown) or Grid View (double-click)

## 🏗️ Project Structure

```
DIXII_processing/
├── 📁 models/                    # AI model implementations
│   ├── donut_classifier.py       # Donut IRS document classifier
│   └── claude_ocr.py            # Claude API integration
├── 📁 utils/                     # Processing utilities
│   └── file_processor.py        # Main document processing logic
├── 📁 templates/                 # Web interface
│   └── index.html               # Main application UI
├── 📁 donut-irs-tax-docs-classifier/  # Pre-trained model files
├── 📁 uploads/                   # Temporary upload storage
├── 📁 processed/                 # Organized output files
├── app.py                       # Flask web application
├── config.py                    # Configuration settings
├── run.py                       # Startup script with dependency checks
└── requirements.txt             # Python dependencies
```

## 🔧 Configuration

### Environment Variables (.env)
```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

### Supported Document Types
- W-9 Request for Taxpayer ID
- Form 1040 Individual Tax Return
- W-2 Wage and Tax Statement
- 1099 Series (1099-MISC, 1099-NEC, etc.)
- Schedule C Profit or Loss
- Schedule K-1 Partner's Share
- And 16+ more tax forms

## 🛡️ Security & Privacy

- **Local Processing**: All documents processed locally on your machine
- **API Security**: Only text content sent to Claude API for extraction
- **No Storage**: Claude API doesn't store your data
- **Environment Variables**: API keys stored securely in `.env` file

## 🐛 Troubleshooting

### Common Issues

**Port 8080 already in use?**
```bash
pkill -f python3
python3 run.py
```

**API Key not working?**
1. Click the ⚙️ settings button
2. Enter your Claude API key (starts with `sk-ant-api03-`)
3. Click "Save Settings"

**Model loading slowly?**
- First run downloads the Donut model (~2GB)
- Subsequent runs are much faster
- Ensure stable internet connection

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Hugging Face**: For the Donut model architecture
- **Anthropic**: For the Claude API
- **Tax Document Classification**: Built on the IRS tax forms dataset

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/yourusername/DIXII_processing/issues)
- 📧 **Email**: your.email@example.com
- 💬 **Discussions**: [GitHub Discussions](https://github.com/yourusername/DIXII_processing/discussions)

---

**Made with ❤️ for tax professionals and document processing enthusiasts** 