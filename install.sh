#!/usr/bin/env bash
# Flux v0.7.0 — Universal Installer for Linux & macOS
# Author: XioDr · License: Apache-2.0 · https://github.com/AlacrityAgency/Flux

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================================${NC}"
echo -e "${GREEN}  Flux v0.7.0 — Linux & macOS Desktop & CLI Installer${NC}"
echo -e "${BLUE}========================================================${NC}"
echo ""

# Detect OS
OS_TYPE="$(uname -s)"
case "${OS_TYPE}" in
    Linux*)     PLATFORM="linux";;
    Darwin*)    PLATFORM="macos";;
    *)          PLATFORM="unknown";;
esac

echo -e "[*] Detected Platform: ${YELLOW}${PLATFORM}${NC} (${OS_TYPE})"

# Check Python 3.10+
PY_CMD=""
for cmd in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY_VERSION=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        PY_MAJOR=$("$cmd" -c 'import sys; print(sys.version_info.major)')
        PY_MINOR=$("$cmd" -c 'import sys; print(sys.version_info.minor)')
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            PY_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PY_CMD" ]; then
    echo -e "${RED}[ERROR] Python 3.10 or higher was not found on your system.${NC}"
    echo "Please install Python 3.10+ using your package manager:"
    if [ "$PLATFORM" = "macos" ]; then
        echo "  brew install python@3.12"
    else
        echo "  sudo apt install python3 python3-pip python3-venv (Ubuntu/Debian)"
        echo "  sudo dnf install python3 python3-pip (Fedora/RHEL)"
        echo "  sudo pacman -S python python-pip (Arch Linux)"
    fi
    exit 1
fi

echo -e "[*] Using Python: ${GREEN}$PY_CMD${NC} (v${PY_VERSION})"

# Resolve Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/share/flux"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

echo -e "[*] Installing to: ${YELLOW}${INSTALL_DIR}${NC}"

# Check or Create Virtual Environment
VENV_DIR="${INSTALL_DIR}/venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "[*] Creating dedicated virtualenv in ${VENV_DIR}..."
    "$PY_CMD" -m venv "$VENV_DIR"
fi

VENV_PY="${VENV_DIR}/bin/python"
VENV_PIP="${VENV_DIR}/bin/pip"

# Install/Update Flux editable or standard package
echo -e "[*] Installing Flux package & dependencies..."
"$VENV_PIP" install --upgrade pip >/dev/null 2>&1 || true
"$VENV_PIP" install -e "${SCRIPT_DIR}[agentic]" --quiet

# Create executable wrappers in ~/.local/bin
cat << 'EOF' > "${BIN_DIR}/flux"
#!/usr/bin/env bash
INSTALL_DIR="${HOME}/.local/share/flux"
exec "${INSTALL_DIR}/venv/bin/python" -m flux "$@"
EOF
chmod +x "${BIN_DIR}/flux"

cat << 'EOF' > "${BIN_DIR}/flux-serve"
#!/usr/bin/env bash
INSTALL_DIR="${HOME}/.local/share/flux"
exec "${INSTALL_DIR}/venv/bin/python" -m flux serve "$@"
EOF
chmod +x "${BIN_DIR}/flux-serve"

echo -e "${GREEN}[+] Created CLI binaries:${NC}"
echo "    - ${BIN_DIR}/flux"
echo "    - ${BIN_DIR}/flux-serve"

# Copy Icon
ICON_SRC="${SCRIPT_DIR}/src/flux/static/flux.svg"
ICON_DST="${INSTALL_DIR}/flux.svg"
if [ -f "$ICON_SRC" ]; then
    cp "$ICON_SRC" "$ICON_DST"
fi

# Platform specific Desktop shortcut
if [ "$PLATFORM" = "linux" ]; then
    APPLICATIONS_DIR="${HOME}/.local/share/applications"
    mkdir -p "$APPLICATIONS_DIR"
    DESKTOP_FILE="${APPLICATIONS_DIR}/flux.desktop"
    cat << EOF > "$DESKTOP_FILE"
[Desktop Entry]
Version=1.0
Type=Application
Name=Flux
GenericName=AI Software Engineering Agent
Comment=Flux v0.7.0 — Agentic Engineering Suite & Parallel Multi-Agent Orchestration
Exec=${BIN_DIR}/flux-serve --port 8000
Icon=${ICON_DST}
Terminal=false
Categories=Development;IDE;Utility;
Keywords=ai;agent;coding;git;gemini;ollama;
EOF
    chmod +x "$DESKTOP_FILE"
    echo -e "${GREEN}[+] Created Linux desktop application launcher:${NC} ${DESKTOP_FILE}"

elif [ "$PLATFORM" = "macos" ]; then
    APP_BUNDLE="${HOME}/Applications/Flux.app"
    mkdir -p "${APP_BUNDLE}/Contents/MacOS"
    mkdir -p "${APP_BUNDLE}/Contents/Resources"
    
    cat << EOF > "${APP_BUNDLE}/Contents/MacOS/Flux"
#!/usr/bin/env bash
"${BIN_DIR}/flux-serve" --port 8000 &
sleep 1
open "http://127.0.0.1:8000"
EOF
    chmod +x "${APP_BUNDLE}/Contents/MacOS/Flux"

    cat << EOF > "${APP_BUNDLE}/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Flux</string>
    <key>CFBundleIdentifier</key>
    <string>agency.alacrity.flux</string>
    <key>CFBundleName</key>
    <string>Flux</string>
    <key>CFBundleVersion</key>
    <string>0.7.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
EOF
    echo -e "${GREEN}[+] Created macOS Application Bundle:${NC} ${APP_BUNDLE}"
fi

# Create Uninstaller script
UNINSTALL_SH="${INSTALL_DIR}/uninstall.sh"
cat << 'EOF' > "$UNINSTALL_SH"
#!/usr/bin/env bash
echo "Uninstalling Flux..."
rm -f "${HOME}/.local/bin/flux"
rm -f "${HOME}/.local/bin/flux-serve"
rm -f "${HOME}/.local/share/applications/flux.desktop"
rm -rf "${HOME}/Applications/Flux.app"
rm -rf "${HOME}/.local/share/flux"
echo "Flux has been completely removed."
EOF
chmod +x "$UNINSTALL_SH"

echo ""
echo -e "${BLUE}========================================================${NC}"
echo -e "${GREEN}  Installation completed successfully!${NC}"
echo -e "${BLUE}========================================================${NC}"
echo ""
echo -e "To ensure ${YELLOW}flux${NC} is accessible in your terminal, make sure ${YELLOW}${BIN_DIR}${NC} is in your PATH:"
echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
echo ""
echo "Quick Commands:"
echo -e "  Start workspace:   ${GREEN}flux serve --port 8000${NC}"
echo -e "  Open setup wizard: ${GREEN}open http://127.0.0.1:8000/setup${NC} (or xdg-open on Linux)"
echo -e "  Headless daemon:   ${GREEN}flux daemon --port 8040${NC}"
echo -e "  Terminal control:  ${GREEN}flux ctl status${NC}"
echo -e "  Uninstall:         ${GREEN}${UNINSTALL_SH}${NC}"
echo ""
