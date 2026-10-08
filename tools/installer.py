import os
from pathlib import Path
import shutil
import sys
import tomllib
import winreg

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def safe_print(text: str = ""):
    try:
        print(text)
    except Exception:
        try:
            enc = sys.stdout.encoding or 'utf-8'
            sys.stdout.buffer.write((text + "\n").encode(enc, errors='replace'))
            sys.stdout.buffer.flush()
        except Exception:
            pass


def install_flux():
    safe_print("=" * 60)
    safe_print("  در حال نصب Flux روی سیستم شما...")
    safe_print("  Installing Flux Desktop for Windows...")
    safe_print("=" * 60)

    # 1. Paths
    repo_root = Path(__file__).resolve().parent.parent
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    install_dir = local_app_data / "Programs" / "Flux"
    install_dir.mkdir(parents=True, exist_ok=True)

    # 2. Icon
    src_ico = repo_root / "src" / "flux" / "static" / "flux-mark.ico"
    dst_ico = install_dir / "flux.ico"
    if src_ico.exists():
        shutil.copy2(src_ico, dst_ico)
        safe_print(f"[+] آیکون برنامه کپی شد / Copied icon: {dst_ico}")

    # 3. Executable
    # Check if compiled binary exists in dist/ or dist/redesign/
    dist_exe = repo_root / "dist" / "local-agents" / "Flux.exe"
    if not dist_exe.exists():
        dist_exe = repo_root / "dist" / "Flux.exe"
    if not dist_exe.exists():
        dist_exe = repo_root / "dist" / "redesign" / "FluxDemo.exe"
    if not dist_exe.exists():
        dist_exe = repo_root / "dist" / "flux.exe"

    target_exe = install_dir / "Flux.exe"
    if dist_exe.exists():
        try:
            if target_exe.exists():
                from datetime import datetime
                backup = install_dir / ("Flux.previous-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".exe")
                shutil.copy2(target_exe, backup)
            shutil.copy2(dist_exe, target_exe)
            safe_print(f"[+] فایل اجرایی کپی شد / Copied binary: {target_exe}")
        except PermissionError:
            raise SystemExit("Flux در حال اجراست؛ آن را ببندید و نصب را دوباره اجرا کنید.")
    else:
        # Create launcher runner batch/python if exe not yet built
        launcher_cmd = f'@echo off\ncd /d "{repo_root}"\npython run_flux.py %*\n'
        launcher_bat = install_dir / "Flux.bat"
        launcher_bat.write_text(launcher_cmd, encoding="ascii", errors="replace")
        target_exe = launcher_bat
        safe_print(f"[!] فایل اجرایی کامپایل‌شده هنوز ساخته نشده؛ لانچر ایجاد شد: {target_exe}")

    # 4. Create Uninstaller script (Pure ASCII batch file to prevent CMD encoding crash)
    uninstall_script = install_dir / "uninstall.bat"
    uninstaller_content = f"""@echo off
setlocal
echo ========================================================
echo   Uninstalling Flux Desktop from Windows...
echo ========================================================
taskkill /F /IM Flux.exe /T >nul 2>&1
taskkill /F /IM FluxDemo.exe /T >nul 2>&1

set "DESKTOP_LNK=%USERPROFILE%\\Desktop\\Flux.lnk"
if exist "%DESKTOP_LNK%" del /f /q "%DESKTOP_LNK%"

set "START_MENU=%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Flux"
if exist "%START_MENU%" rd /s /q "%START_MENU%"

reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Flux" /f >nul 2>&1

echo.
echo Flux has been successfully uninstalled from your system.
echo Cleaning up application directory...
echo.
timeout /t 2 >nul
rd /s /q "{install_dir}" >nul 2>&1
exit
"""
    uninstall_script.write_text(uninstaller_content, encoding="ascii", errors="replace")
    safe_print(f"[+] فایل حذف نصب (Uninstaller) ایجاد شد: {uninstall_script}")

    # 5. Create Windows Shortcuts (Desktop & Start Menu) using PowerShell
    desktop_lnk = Path(os.environ.get("USERPROFILE", Path.home())) / "Desktop" / "Flux.lnk"
    start_menu_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Flux"
    start_menu_dir.mkdir(parents=True, exist_ok=True)
    start_menu_lnk = start_menu_dir / "Flux.lnk"

    ps_script = f"""
    $WshShell = New-Object -ComObject WScript.Shell

    # Desktop Shortcut
    $Shortcut = $WshShell.CreateShortcut('{desktop_lnk}')
    $Shortcut.TargetPath = '{target_exe}'
    $Shortcut.WorkingDirectory = '{install_dir}'
    $Shortcut.IconLocation = '{dst_ico},0'
    $Shortcut.Description = 'Flux — AI assistants and research workspace'
    $Shortcut.Save()

    # Start Menu Shortcut
    $Shortcut2 = $WshShell.CreateShortcut('{start_menu_lnk}')
    $Shortcut2.TargetPath = '{target_exe}'
    $Shortcut2.WorkingDirectory = '{install_dir}'
    $Shortcut2.IconLocation = '{dst_ico},0'
    $Shortcut2.Description = 'Flux — AI assistants and research workspace'
    $Shortcut2.Save()
    """

    import subprocess
    ps_proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
    if ps_proc.returncode == 0:
        safe_print(f"[+] میانبر دسکتاپ ایجاد شد / Desktop shortcut: {desktop_lnk}")
        safe_print(f"[+] میانبر منوی استارت ایجاد شد / Start Menu shortcut: {start_menu_lnk}")
    else:
        safe_print(f"[-] خطا در ایجاد میانبرها: {ps_proc.stderr}")

    # 6. Register in Windows Registry for Add/Remove Programs (Installed apps)
    try:
        reg_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Flux"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Flux — AI workspace")
            version=tomllib.loads((repo_root/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Alacrity Flux")
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(dst_ico))
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_script}"')
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 48000)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        safe_print("[+] در لیست برنامه‌های نصب‌شدهٔ ویندوز (Installed apps) ثبت شد.")
    except Exception as e:
        safe_print(f"[-] هشدار ثبت در رجیستری: {e}")

    safe_print("\n" + "=" * 60)
    safe_print("  تبریک! نرم‌افزار Flux با موفقیت روی ویندوز شما نصب شد.")
    safe_print("  اکنون می‌توانید Flux را از منوی Start یا آیکون دسکتاپ اجرا کنید.")
    safe_print("=" * 60)


if __name__ == "__main__":
    install_flux()
