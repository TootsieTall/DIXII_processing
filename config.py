import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Configuration
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    
    # Model Configuration
    DONUT_MODEL_PATH = 'hsarfraz/donut-irs-tax-docs-classifier'
    
    # File Processing Configuration
    UPLOAD_FOLDER = 'uploads'
    PROCESSED_FOLDER = 'processed'
    MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'}
    
    # Image Processing Configuration
    TARGET_WIDTH = 1920
    TARGET_HEIGHT = 2560
    
    # SPEED OPTIMIZATION Configuration
    ENABLE_SPEED_OPTIMIZATIONS = True
    SKIP_VALIDATION_HIGH_CONFIDENCE = 0.9  # Skip validation above this confidence
    SKIP_VALIDATION_SIMPLE_DOCS = 0.7      # Skip validation for simple docs above this confidence
    SKIP_PREPROCESSING_HIGH_CONFIDENCE = 0.85  # Skip preprocessing above this confidence
    SKIP_PREPROCESSING_SIMPLE_DOCS = 0.7   # Skip preprocessing for simple docs above this confidence
    USE_COMBINED_EXTRACTION = True          # Use single API call for multiple fields
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    
    # Upload Cleanup Configuration
    ENABLE_UPLOAD_CLEANUP = True
    UPLOAD_CLEANUP_AGE_HOURS = 1  # Remove files older than 1 hour (more aggressive cleanup)
    
    # Session Cleanup Configuration
    ENABLE_SESSION_CLEANUP = True
    SESSION_CLEANUP_AGE_HOURS = 2  # Remove completed/error sessions older than 2 hours
    STUCK_SESSION_CLEANUP_AGE_HOURS = 1  # Remove stuck sessions older than 1 hour
    
    @staticmethod
    def init_app(app):
        # Create necessary directories
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.PROCESSED_FOLDER, exist_ok=True) 