import sys
from pathlib import Path

# preparation.py lives at the repo root (one level above IVE/), not inside the
# IVE package. Make it importable for legacy tests in this directory.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
