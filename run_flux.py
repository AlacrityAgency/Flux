"""Launch the Flux personal window by default; explicit arguments use the CLI."""
import os
from pathlib import Path
import sys

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
else:
    # Windowed PyInstaller apps have no console streams; keep diagnostics local.
    log_dir = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'FluxDemo'
    log_dir.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = log_dir.joinpath('desktop.log').open('a', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = sys.stdout

if __name__ == '__main__':
    if len(sys.argv) == 1:
        from flux.desktop import launch
        launch()
    else:
        from flux.cli import main
        main()
