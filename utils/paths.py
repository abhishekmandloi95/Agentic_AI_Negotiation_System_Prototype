"""Paths anchored to this checkout, independent of the shell working directory."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
def project_path(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path
