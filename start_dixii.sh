#!/bin/bash

# DIXII - AI Document Processor Startup Script
# For Mac and Linux users

clear

echo ""
echo "==============================================="
echo "🏛️  DIXII - AI Tax Document Processing System"
echo "==============================================="
echo ""

echo "📦 Installing required AI tools..."
echo "This may take a few minutes on first run..."
echo ""

# Try to install dependencies
if pip3 install -r requirements.txt; then
    echo ""
    echo "✅ Installation complete!"
elif pip install -r requirements.txt; then
    echo ""
    echo "✅ Installation complete!"
else
    echo ""
    echo "❌ Could not install dependencies. Please check:"
    echo "   1. Python is installed properly"
    echo "   2. You have internet connection" 
    echo "   3. Try running with sudo (e.g., sudo ./start_dixii.sh)"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

echo ""
echo "🚀 Starting DIXII..."
echo ""
echo "Once started, open your browser to: http://localhost:8080"
echo ""
echo "⚠️  Keep this terminal window open while using DIXII"
echo "   Close this window or press Ctrl+C to stop DIXII"
echo ""

# Try to start with python3 first, then python
if command -v python3 &> /dev/null; then
    python3 run.py
elif command -v python &> /dev/null; then
    python run.py
else
    echo "❌ Python not found. Please install Python first."
    echo "   Go to: https://www.python.org/downloads/"
    read -p "Press Enter to exit..."
    exit 1
fi 