# 🚀 DIXII - Super Easy Setup Guide

**Turn your computer into an AI-powered document processor in 3 simple steps!**

No coding experience needed. Just follow along step by step.

---

## 📋 What You Need

- A computer (Windows, Mac, or Linux)
- Internet connection
- 10 minutes of your time

## 🎯 What This Does

DIXII will help you:
- ✅ Read tax documents automatically (W-2, 1099, K-1, etc.)
- ✅ Extract important information like names, amounts, dates
- ✅ Organize everything neatly
- ✅ Save you hours of manual data entry

---

## 📱 Step 1: Get Python (The Engine)

Python is like the engine that makes DIXII work. Don't worry - it's free and safe!

### 🍎 **For Mac Users:**
1. Open your web browser
2. Go to: https://www.python.org/downloads/
3. Click the big yellow "Download Python" button
4. Open the downloaded file and follow the installer
5. ✅ **Important:** Make sure to check "Add Python to PATH" during installation

### 🪟 **For Windows Users:**
1. Open your web browser  
2. Go to: https://www.python.org/downloads/
3. Click the big yellow "Download Python" button
4. Open the downloaded file
5. ✅ **VERY IMPORTANT:** Check the box that says "Add Python to PATH"
6. Click "Install Now"

### 🐧 **For Linux Users:**
Open Terminal and type:
```bash
sudo apt update
sudo apt install python3 python3-pip
```

---

## 📁 Step 2: Get DIXII Files

### Option A: Download ZIP (Easiest)
1. If someone sent you DIXII files, extract the ZIP to your Desktop
2. You should see a folder called "DIXII_processing"

### Option B: Get from Internet
1. Open your web browser
2. Go to the DIXII download link (ask whoever gave you this guide)
3. Download and extract to your Desktop

---

## ⚡ Step 3: Start DIXII

### 🎯 **Super Easy Way (Recommended):**

Just double-click one of these files in your DIXII folder:
- **Windows:** Double-click `start_dixii.bat`
- **Mac/Linux:** Double-click `start_dixii.sh`

These will do everything automatically! Skip to Step 4 if this works.

### 🔧 **Manual Way (if auto doesn't work):**

### 🍎 **Mac Users:**
1. Press `Cmd + Space` to open Spotlight
2. Type "Terminal" and press Enter
3. A black window opens - don't worry, this is normal!
4. Type this exactly (copy and paste works too):
   ```bash
   cd Desktop/DIXII_processing
   ```
   Press Enter

5. Type this:
   ```bash
   pip3 install -r requirements.txt
   ```
   Press Enter and wait (this downloads the AI tools)

6. Finally, type this:
   ```bash
   python3 run.py
   ```
   Press Enter

### 🪟 **Windows Users:**
1. Press `Windows Key + R`
2. Type "cmd" and press Enter
3. A black window opens - this is normal!
4. Type this exactly:
   ```bash
   cd Desktop\DIXII_processing
   ```
   Press Enter

5. Type this:
   ```bash
   pip install -r requirements.txt
   ```
   Press Enter and wait (this downloads the AI tools)

6. Finally, type this:
   ```bash
   python run.py
   ```
   Press Enter

---

## 🌐 Step 4: Open DIXII in Your Browser

1. You should see text like "Running on http://127.0.0.1:8080"
2. Open your web browser (Chrome, Safari, Firefox, etc.)
3. Type this in the address bar:
   ```
   localhost:8080
   ```
4. Press Enter

**🎉 SUCCESS!** You should see the DIXII interface!

---

## 🔧 Quick Setup (Optional but Recommended)

### Add Your AI Key:
1. In DIXII, click "Settings" 
2. Get a Claude API key from: https://console.anthropic.com/
3. Paste it in the "Claude API Key" field
4. Click "Save"

*Without this key, DIXII will still work but with limited features.*

---

## 🆘 Help! Something Went Wrong?

### "Python not found" or "Command not recognized"
- **Solution:** Python isn't installed properly
- **Fix:** Go back to Step 1 and make sure you checked "Add to PATH"

### "Permission denied" or "Access denied"
- **Solution:** Your computer is blocking the installation
- **Fix:** Try running as administrator (Windows) or use `sudo` (Mac/Linux)

### "pip not found"
- **Windows:** Try `python -m pip` instead of just `pip`
- **Mac/Linux:** Try `pip3` instead of `pip`

### The black window closed immediately
- **Solution:** There was an error
- **Fix:** Try the steps again, or restart your computer and try again

### Browser shows "Can't connect" or "Page not found"
- **Solution:** DIXII isn't running
- **Fix:** Make sure the black window (Terminal/Command Prompt) is still open
- **Try:** Type `python3 run.py` (Mac) or `python run.py` (Windows) again

---

## 📞 Still Need Help?

1. Take a screenshot of any error messages
2. Note which step you're stuck on
3. Ask whoever gave you this guide for help

Remember: Everyone gets stuck sometimes! Don't give up - you're closer than you think! 💪

---

## 🎯 What's Next?

Once DIXII is running:
1. Click "Upload Documents" 
2. Drag and drop your tax documents
3. Watch the AI magic happen!
4. Download your organized results

**Pro Tip:** Keep the black window (Terminal/Command Prompt) open while using DIXII. If you close it, DIXII stops working. 