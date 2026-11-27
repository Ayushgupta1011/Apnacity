from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent
COMPLAINT_UPLOAD_DIR = BASE_DIR / "uploads" / "complaints"

def create_complaint_photo_folders(complaint_id):
    """Create photo folders for a complaint."""

    complaint_id = str(complaint_id).strip()

    if not re.fullmatch(r"[A-Za-z0-9_-]+", complaint_id):
        raise ValueError("Invalid complaint ID")

    complaint_dir = COMPLAINT_UPLOAD_DIR / complaint_id

    for folder in ("before", "after", "evidence"):
        (complaint_dir / folder).mkdir(parents=True, exist_ok=True)

    return complaint_dir