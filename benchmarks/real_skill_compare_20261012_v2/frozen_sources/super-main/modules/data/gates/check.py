import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core" / "lib"))
from projectchecks import main

if __name__ == "__main__":
    sys.exit(main({"data.integration", "data.restore"}))
