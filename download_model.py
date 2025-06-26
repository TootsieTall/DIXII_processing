#!/usr/bin/env python3
"""
Download the Donut IRS Tax Documents Classifier model.

This script downloads the pre-trained Donut model from Hugging Face
that is required for document classification.
"""

import os
import sys
from pathlib import Path

def download_model():
    """Download the Donut model from Hugging Face"""
    print("🤖 Downloading Donut IRS Tax Documents Classifier...")
    print("=" * 60)
    
    try:
        from huggingface_hub import snapshot_download
        
        # Download the model to the local directory
        model_path = "donut-irs-tax-docs-classifier"
        
        print(f"📥 Downloading model to: {model_path}")
        print("⏳ This may take a few minutes (model is ~2GB)...")
        
        snapshot_download(
            repo_id="AdamCodd/donut-irs-tax-docs-classifier",
            local_dir=model_path,
            local_dir_use_symlinks=False
        )
        
        print("✅ Model downloaded successfully!")
        print(f"📁 Model location: {os.path.abspath(model_path)}")
        
    except ImportError:
        print("❌ Error: huggingface_hub not installed")
        print("Please install it with: pip install huggingface_hub")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        print("\n🔧 Manual download instructions:")
        print("1. Visit: https://huggingface.co/AdamCodd/donut-irs-tax-docs-classifier")
        print("2. Click 'Download repository' or use git:")
        print("   git clone https://huggingface.co/AdamCodd/donut-irs-tax-docs-classifier")
        print("3. Move the downloaded folder to this project directory")
        sys.exit(1)

if __name__ == "__main__":
    # Check if model already exists
    if os.path.exists("donut-irs-tax-docs-classifier"):
        print("✅ Donut model already exists!")
        print("📁 Location: donut-irs-tax-docs-classifier/")
        
        # Check if it has the required files
        required_files = ["config.json", "model.safetensors", "tokenizer.json"]
        missing_files = [f for f in required_files if not os.path.exists(f"donut-irs-tax-docs-classifier/{f}")]
        
        if missing_files:
            print(f"⚠️  Warning: Missing files: {missing_files}")
            print("🔄 Re-downloading model...")
            download_model()
        else:
            print("🎉 Model is ready to use!")
    else:
        download_model() 