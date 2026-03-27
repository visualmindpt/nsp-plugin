# 🚀 NSP Control Center - Build Instructions

Modern desktop application built with **Tauri + Rust + Web Technologies**.

## ✨ Features

- 🎨 **Modern Liquid Glass UI** (Apple-inspired design)
- ⚙️ **Server Control** (Start/Stop inference server)
- 🚨 **Panic Button** (Emergency kill all Python processes)
- 📊 **Real-time System Metrics** (CPU, Memory, Uptime)
- 📝 **Live Logs** with toast notifications
- 🔄 **Auto-status monitoring**
- 🌍 **Cross-platform** (macOS & Windows ready)

---

## 📋 Prerequisites

### macOS
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install Node.js (if not installed)
brew install node

# Xcode Command Line Tools (if not installed)
xcode-select --install
```

### Windows
```powershell
# Install Rust from https://rustup.rs/

# Install Node.js from https://nodejs.org/

# Install Visual Studio C++ Build Tools
# https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

---

## 🏗️ Build Steps

### Development Mode

```bash
cd control-center-v2/desktop

# Install dependencies
npm install

# Run in dev mode
npm run tauri dev
```

### Production Build

```bash
cd control-center-v2/desktop

# Build for production
npm run tauri build
```

**Output locations:**
- **macOS:** `src-tauri/target/release/bundle/macos/NSP-Control-Center.app`
- **Windows:** `src-tauri/target/release/bundle/msi/NSP-Control-Center_2.0.0_x64_en-US.msi`

---

## 🎯 Quick Start

### Option 1: Run from Source
```bash
cd control-center-v2/desktop
npm run tauri dev
```

### Option 2: Run Built App (macOS)
```bash
# After building
open src-tauri/target/release/bundle/macos/NSP-Control-Center.app
```

### Option 3: Run Built App (Windows)
```powershell
# Install the MSI package
.\src-tauri\target\release\bundle\msi\NSP-Control-Center_2.0.0_x64_en-US.msi
```

---

## 🔧 Configuration

The app automatically detects the NSP Plugin project directory. If needed, you can configure:

**File:** `src-tauri/tauri.conf.json`

```json
{
  "app": {
    "windows": [
      {
        "title": "NSP Control Center",
        "width": 1200,
        "height": 800
      }
    ]
  }
}
```

---

## 🎨 UI Features

### Server Control Panel
- **Start Server:** Launches Python inference server on port 5001
- **Stop Server:** Gracefully stops the server
- **Check Status:** Verify server state and PID
- **Auto-refresh:** Status updates every 5 seconds

### Panic Button 🚨
Emergency shutdown of ALL Python processes:
- macOS: `pkill -9 python`
- Windows: `taskkill /F /IM python.exe`

⚠️ **Warning:** This kills ALL Python processes system-wide!

### System Metrics
Real-time monitoring:
- **CPU Usage:** Total system CPU load
- **Memory:** Used/Total MB with percentage
- **Uptime:** Server runtime (HH:MM:SS)
- **Predictions:** Today's prediction count

### Logs
- Real-time system logs
- Color-coded entries
- Timestamp for each event
- Auto-scroll with limit (100 entries)
- Clear logs button

---

## 🐛 Troubleshooting

### Build Fails

**Error:** "Could not find `cargo`"
```bash
# Ensure Rust is in PATH
source $HOME/.cargo/env

# Or restart terminal after installing Rust
```

**Error:** "Could not compile dependency"
```bash
# Clean and rebuild
cd control-center-v2/desktop
rm -rf src-tauri/target
npm run tauri build
```

### Server Won't Start

**Issue:** "Erro ao obter diretório"
- Ensure you're running from the correct project directory
- The app expects: `NSP Plugin_dev_full_package/control-center-v2/`

**Issue:** "venv not found"
- Ensure Python virtual environment is set up:
```bash
cd ../../
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Panic Button Not Working

**macOS:**
- Requires Terminal permissions
- System Preferences > Security & Privacy > Privacy > Full Disk Access

**Windows:**
- Run as Administrator if needed

---

## 📦 Distribution

### macOS

Create DMG for distribution:
```bash
npm run tauri build

# Creates: src-tauri/target/release/bundle/dmg/NSP-Control-Center_2.0.0_x64.dmg
```

**Code Signing** (optional):
```bash
codesign --sign "Developer ID Application: YourName" \
  src-tauri/target/release/bundle/macos/NSP-Control-Center.app
```

### Windows

MSI installer is automatically created:
```
src-tauri/target/release/bundle/msi/NSP-Control-Center_2.0.0_x64_en-US.msi
```

---

## 🎯 Architecture

```
NSP Control Center (Tauri Desktop App)
│
├── Rust Backend (src-tauri/src/lib.rs)
│   ├── start_inference_server()
│   ├── stop_inference_server()
│   ├── server_status()
│   ├── panic_button()
│   └── get_system_metrics()
│
├── Frontend (static/index.html)
│   ├── Liquid Glass UI (CSS with backdrop-filter)
│   ├── Real-time status updates
│   ├── Interactive controls
│   └── Toast notifications
│
└── Python Inference Server (port 5001)
    ├── FastAPI + PyTorch
    ├── Model inference
    └── Feedback system
```

---

## 🚢 Release Checklist

- [ ] Test on macOS (Intel & Apple Silicon)
- [ ] Test on Windows (x64)
- [ ] Verify all Rust commands work
- [ ] Test panic button (carefully!)
- [ ] Check metrics accuracy
- [ ] Verify server start/stop
- [ ] Test with actual inference server
- [ ] Update version in `tauri.conf.json`
- [ ] Code sign (if distributing)
- [ ] Create release notes

---

## 📞 Support

**Issues:** https://github.com/your-repo/issues
**Docs:** control-center-v2/README.md

---

**Built with ❤️ using Tauri**
**Version:** 2.0.0
**Date:** 21 Novembro 2025
