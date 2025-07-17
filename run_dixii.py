#!/usr/bin/env python3
"""
Dixii Tax Document Processor Launcher
=====================================

This script helps you start the appropriate version of the Dixii tax document processor.

Usage:
    python run_dixii.py [--enhanced] [--legacy] [--port PORT]
    
Options:
    --enhanced     Start the enhanced system (default, recommended)
    --legacy       Start the legacy system (deprecated)
    --port PORT    Specify port number (default: 8080)
    --help         Show this help message
"""

import sys
import subprocess
import argparse
import os
from pathlib import Path

def print_banner():
    """Print application banner"""
    print("=" * 60)
    print("🏛️  Dixii Tax Document Processing System")
    print("=" * 60)

def check_system_status():
    """Check which systems are available"""
    project_root = Path(__file__).parent
    
    enhanced_available = (project_root / 'enhanced_app.py').exists()
    legacy_available = (project_root / 'app.py').exists()
    
    return enhanced_available, legacy_available

def show_system_info():
    """Show information about available systems"""
    enhanced_available, legacy_available = check_system_status()
    
    print("\n📊 Available Systems:")
    
    if enhanced_available:
        print("✅ Enhanced System (enhanced_app.py)")
        print("   • Advanced entity recognition")
        print("   • Form-specific processing")
        print("   • Intelligent filename generation")
        print("   • Real-time progress tracking")
        print("   • Modern web interface")
    else:
        print("❌ Enhanced System not found")
    
    if legacy_available:
        print("⚠️  Legacy System (app.py) - DEPRECATED")
        print("   • Basic document processing")
        print("   • Simple progress tracking")
        print("   • Will be removed in future version")
    else:
        print("❌ Legacy System not found")
    
    print()

def start_enhanced_system(port=8080):
    """Start the enhanced system"""
    print("🚀 Starting Enhanced Dixii Processor...")
    print(f"   URL: http://localhost:{port}")
    print("   Features: Advanced AI processing, entity recognition, smart filenames")
    print()
    
    try:
        subprocess.run([sys.executable, 'enhanced_app.py', '--port', str(port)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start enhanced system: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Enhanced system stopped by user")
    except FileNotFoundError:
        print("❌ enhanced_app.py not found. Please ensure the enhanced system is installed.")
        print("   Run: python enhanced_setup.py")
        sys.exit(1)

def start_legacy_system(port=8080):
    """Start the legacy system"""
    print("⚠️  DEPRECATION WARNING ⚠️")
    print("You are starting the LEGACY system which is deprecated!")
    print("Please migrate to the enhanced system for better features and accuracy.")
    print("See MIGRATION_GUIDE.md for migration instructions.")
    print()
    
    response = input("Do you want to continue with the legacy system? (y/N): ")
    if response.lower() not in ['y', 'yes']:
        print("👍 Good choice! Starting enhanced system instead...")
        start_enhanced_system(port)
        return
    
    print("🏚️  Starting Legacy Dixii Processor...")
    print(f"   URL: http://localhost:{port}")
    print("   Note: Limited features, will be removed in future version")
    print()
    
    try:
        subprocess.run([sys.executable, 'app.py'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start legacy system: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Legacy system stopped by user")
    except FileNotFoundError:
        print("❌ app.py not found")
        sys.exit(1)

def show_setup_help():
    """Show setup help for new users"""
    print("🛠️  First Time Setup:")
    print()
    print("1. Install the enhanced system:")
    print("   python enhanced_setup.py --api-key YOUR_CLAUDE_API_KEY")
    print()
    print("2. Or install without API key and configure later:")
    print("   python enhanced_setup.py")
    print()
    print("3. Test the system:")
    print("   python test_enhanced_system.py")
    print()
    print("4. Start processing:")
    print("   python run_dixii.py")
    print()

def main():
    """Main launcher function"""
    parser = argparse.ArgumentParser(
        description="Dixii Tax Document Processor Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        '--enhanced',
        action='store_true',
        help='Start the enhanced system (default)'
    )
    
    parser.add_argument(
        '--legacy',
        action='store_true', 
        help='Start the legacy system (deprecated)'
    )
    
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port number to run on (default: 8080)'
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Show system information and exit'
    )
    
    parser.add_argument(
        '--setup-help',
        action='store_true',
        help='Show setup instructions and exit'
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    # Show setup help
    if args.setup_help:
        show_setup_help()
        return
    
    # Show system info
    if args.info:
        show_system_info()
        return
    
    enhanced_available, legacy_available = check_system_status()
    
    # Check if any system is available
    if not enhanced_available and not legacy_available:
        print("❌ No Dixii systems found!")
        print()
        show_setup_help()
        sys.exit(1)
    
    # Determine which system to start
    if args.legacy and args.enhanced:
        print("❌ Cannot specify both --legacy and --enhanced")
        sys.exit(1)
    
    if args.legacy:
        if not legacy_available:
            print("❌ Legacy system not found!")
            sys.exit(1)
        start_legacy_system(args.port)
    elif args.enhanced or (not args.legacy and enhanced_available):
        if not enhanced_available:
            print("❌ Enhanced system not found!")
            if legacy_available:
                print("   Legacy system is available but deprecated.")
                print("   Run with --legacy to use it, or install enhanced system.")
            show_setup_help()
            sys.exit(1)
        start_enhanced_system(args.port)
    else:
        # Default to legacy if only legacy is available
        if legacy_available:
            print("⚠️  Only legacy system found. Enhanced system recommended!")
            print("   Install enhanced system with: python enhanced_setup.py")
            print()
            start_legacy_system(args.port)
        else:
            print("❌ No systems available!")
            show_setup_help()
            sys.exit(1)

if __name__ == '__main__':
    main() 