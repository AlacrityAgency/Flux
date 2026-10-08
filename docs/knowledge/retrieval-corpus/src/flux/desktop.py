"""Windows app-window launcher; the local engine exits when its window closes."""
import ctypes
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import tempfile
import shutil
import webbrowser
import psutil

from flux.settings import get_settings


def launch():
    data = Path(get_settings().db_path).resolve().parent
    data.mkdir(parents=True, exist_ok=True)
    lock_file = data.joinpath('desktop.lock')
    if not lock_file.exists():
        try:
            lock_file.write_bytes(b'0')
        except Exception:
            pass
    try:
        lock = lock_file.open('a+b')
    except Exception:
        lock = None

    if sys.platform == 'win32' and lock:
        import msvcrt
        try:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except (OSError, PermissionError):
            ctypes.windll.user32.MessageBoxW(0, 'Flux در حال اجرا است. پنجرهٔ باز برنامه را انتخاب کنید.', 'Flux', 0)
            try:
                lock.close()
            except Exception:
                pass
            return
    try:
        browser_profile = None
        import uvicorn
        from flux.api.app import create_app
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        config = uvicorn.Config(create_app(), host='127.0.0.1', port=port, log_level='warning', access_log=False)
        server = uvicorn.Server(config)
        worker = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        worker.start()
        deadline = time.monotonic()+15
        while not server.started and worker.is_alive() and time.monotonic()<deadline:
            time.sleep(.05)
        if not server.started:
            raise RuntimeError('Local engine did not start')
        url = f'http://127.0.0.1:{port}'
        candidates = [
            Path(os.environ.get('PROGRAMFILES', 'C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('LOCALAPPDATA', ''))/'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('PROGRAMFILES', 'C:/Program Files'))/'Google/Chrome/Application/chrome.exe',
            Path(os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)'))/'Google/Chrome/Application/chrome.exe',
            Path(os.environ.get('LOCALAPPDATA', ''))/'Google/Chrome/Application/chrome.exe',
        ]
        executable = next((p for p in candidates if p.exists()), None)
        try:
            if executable:
                browser_profile = data / 'flux-profile'
                browser_profile.mkdir(parents=True, exist_ok=True)
                app_url = f'{url}/?desktop=1'
                process = subprocess.Popen([str(executable), '--app='+app_url,
                    '--user-data-dir='+str(browser_profile), '--window-size=1360,880',
                    '--no-first-run', '--disable-extensions', '--disable-background-mode'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                profile_text = str(browser_profile).lower()
                appeared = False
                empty_streak = 0
                launch_deadline = time.monotonic() + 15
                while worker.is_alive():
                    if process.poll() is None:
                        appeared = True
                        empty_streak = 0
                        time.sleep(0.5)
                        continue

                    matching_count = 0
                    for candidate in psutil.process_iter(["pid", "cmdline"]):
                        try:
                            command = " ".join(candidate.info.get("cmdline") or []).lower()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                        if profile_text in command:
                            matching_count += 1

                    if matching_count > 0:
                        appeared = True
                        empty_streak = 0
                    elif appeared:
                        empty_streak += 1
                        if empty_streak >= 3:
                            break
                    elif time.monotonic() >= launch_deadline:
                        raise RuntimeError("The Flux app window did not start.")
                    time.sleep(0.5)
            else:
                webbrowser.open(url)
                # Fallback browser does not provide a window lifetime handle.
                worker.join()
        finally:
            server.should_exit = True
            worker.join(timeout=8)
            try:
                sock.close()
            except Exception:
                pass
    finally:
        if lock:
            try:
                lock.close()
            except Exception:
                pass
