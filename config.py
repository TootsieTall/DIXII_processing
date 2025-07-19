import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API Configuration
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

    # Supabase Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL', 'https://zzslwlitkosljnbfuoef.supabase.co')
    SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp6c2x3bGl0a29zbGpuYmZ1b2VmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTEyNTk5NDAsImV4cCI6MjA2NjgzNTk0MH0.8mdSzYZ35iHPaJ1ddfw0NvEeWM-VlBd-CQe9ShoMp-w')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp6c2x3bGl0a29zbGpuYmZ1b2VmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTI1OTk0MCwiZXhwIjoyMDY2ODM1OTQwfQ.P4Uk6FRc0fBbxl-LJE8GrSK8JHI4RCyoFs43cvhfwEM')

    # Model Configuration
    DONUT_MODEL_PATH = './donut-irs-tax-docs-classifier'

    # File Processing Configuration
    UPLOAD_FOLDER = 'uploads'
    PROCESSED_FOLDER = 'processed'
    MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'}

    # Image Processing Configuration
    TARGET_WIDTH = 1920
    TARGET_HEIGHT = 2560

    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')

    @staticmethod
    def init_app(app):
        # Create necessary directories
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.PROCESSED_FOLDER, exist_ok=True)