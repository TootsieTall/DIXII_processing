#!/usr/bin/env python3
"""
DIXII Pro - Modern Tax Document Processor Launcher
=================================================

This script launches the modernized DIXII tax document processing system
with a sleek, professional 2024/2025 interface design.

Features:
- Modern glassmorphism interface
- Dark mode support with system preference detection
- Smooth animations and micro-interactions
- Enhanced responsive design
- Professional gradient backgrounds
"""

import os
import sys
import time
import webbrowser
from pathlib import Path

def print_banner():
    """Print a modern banner for DIXII Pro"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                      🚀 DIXII Pro                        ║
║              Modern Tax Document Processor               ║
║                                                          ║
║  ✨ 2024/2025 Modern Design                             ║
║  🎨 Glassmorphism Interface                             ║
║  🌙 Dark Mode Support                                   ║
║  📱 Responsive Design                                   ║
║  ⚡ Smooth Animations                                   ║
╚═══════════════════════════════════════════════════════════╝
"""
    print(banner)

def check_requirements():
    """Check if all requirements are met"""
    print("🔍 Checking requirements...")
    
    # Check if enhanced_app.py exists
    if not os.path.exists('enhanced_app.py'):
        print("❌ Error: enhanced_app.py not found!")
        print("   Please ensure you're running this from the DIXII project directory.")
        return False
    
    # Check if modern template exists
    modern_template = Path('templates/modern_enhanced_index.html')
    if not modern_template.exists():
        print("❌ Error: Modern template not found!")
        print("   The modern interface template is missing.")
        return False
    
    # Check required Python modules
    required_modules = ['flask', 'anthropic', 'PIL']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ Missing required modules: {', '.join(missing_modules)}")
        print("   Run: pip install -r requirements.txt")
        return False
    
    print("✅ All requirements met!")
    return True

def display_interface_info():
    """Display information about the modern interface"""
    print("\n🎨 Modern Interface Features:")
    print("   • Glassmorphism design with blurred backgrounds")
    print("   • Professional gradient color schemes")
    print("   • Dark mode with system preference detection")
    print("   • Smooth animations and micro-interactions")
    print("   • Mobile-responsive design")
    print("   • Modern typography (Inter font family)")
    print("   • Enhanced user feedback and loading states")

def display_access_info():
    """Display how to access different interfaces"""
    print("\n🌐 Access URLs:")
    print("   🚀 Modern Interface (Recommended):")
    print("      http://localhost:8080/")
    print("   ")
    print("   📄 Legacy Interface (Backward Compatibility):")
    print("      http://localhost:8080/legacy")
    print("   ")
    print("   🔧 API Health Check:")
    print("      http://localhost:8080/api/health")

def check_api_setup():
    """Check if Claude API is configured"""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("\n⚠️  Claude API Setup:")
        print("   To use enhanced AI processing, set your Claude API key:")
        print("   export ANTHROPIC_API_KEY='your-api-key-here'")
        print("   ")
        print("   The system will still work with basic processing without it.")
    else:
        print("✅ Claude API key configured!")

def launch_application():
    """Launch the DIXII Pro application"""
    print("\n🚀 Launching DIXII Pro...")
    print("   Starting Flask development server...")
    print("   Press Ctrl+C to stop the server")
    print("\n" + "="*60)
    
    try:
        # Import and run the enhanced app
        sys.path.insert(0, os.getcwd())
        from enhanced_app import app, init_enhanced_processor
        
        # Initialize the enhanced processor
        init_enhanced_processor()
        
        # Open browser automatically after a short delay
        def open_browser():
            time.sleep(2)
            try:
                webbrowser.open('http://localhost:8080/')
                print("🌐 Browser opened automatically")
            except:
                print("ℹ️  Please open http://localhost:8080/ in your browser")
        
        import threading
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Run the Flask app
        app.run(
            debug=True,
            host='0.0.0.0',
            port=8080,
            use_reloader=False  # Disable reloader to prevent double launch
        )
        
    except KeyboardInterrupt:
        print("\n\n👋 DIXII Pro stopped. Thank you for using our modern interface!")
    except Exception as e:
        print(f"\n❌ Error launching application: {e}")
        print("   Please check the error details and try again.")

def show_tips():
    """Show helpful tips for using the modern interface"""
    print("\n💡 Modern Interface Tips:")
    print("   • Use the theme toggle (🌙) in the header to switch between light/dark modes")
    print("   • Drag and drop files directly onto the upload area")
    print("   • Watch for smooth animations and hover effects throughout the interface")
    print("   • The interface automatically adapts to your screen size")
    print("   • Processing progress is shown with modern animated indicators")
    print("   • All components support keyboard navigation for accessibility")

def main():
    """Main function to launch DIXII Pro"""
    print_banner()
    
    if not check_requirements():
        sys.exit(1)
    
    check_api_setup()
    display_interface_info()
    display_access_info()
    show_tips()
    
    print("\n" + "="*60)
    input("Press Enter to launch DIXII Pro with the modern interface...")
    
    launch_application()

if __name__ == '__main__':
    main() 