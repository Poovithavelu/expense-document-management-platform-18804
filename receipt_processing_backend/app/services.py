import hashlib
import os
import re
from datetime import datetime
from typing import Optional, Tuple, Dict

from .models import db, DocumentVersion, Extraction, Category, DocumentCategory, Job, AuditLog


def ensure_dirs(path: str):
    """Ensure the directory for the given path exists."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def compute_checksum(file_path: str) -> str:
    """Compute SHA256 checksum for a file at file_path."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def save_file(upload_dir: str, document_id: int, version_number: int, filename: str, file_stream) -> Tuple[str, str]:
    """
    Save uploaded file to disk under document/version folders.
    Returns (storage_path, checksum)
    """
    safe_name = os.path.basename(filename)
    target_dir = os.path.join(upload_dir, str(document_id), str(version_number))
    os.makedirs(target_dir, exist_ok=True)
    storage_path = os.path.join(target_dir, safe_name)
    file_stream.seek(0)
    with open(storage_path, "wb") as f:
        f.write(file_stream.read())
    checksum = compute_checksum(storage_path)
    return storage_path, checksum


def naive_ocr_text_from_file(file_path: str) -> str:
    """
    Mock OCR implementation.
    In real deployment integrate Tesseract or a managed OCR service.
    For now, just return filename as text and a stub data.
    """
    base = os.path.basename(file_path)
    # Provide deterministic pseudo text
    return f"Receipt file: {base}\nVendor: ACME Corp\nDate: 2024-05-24\nTotal: USD 123.45"


def parse_receipt(text: str) -> Dict:
    """
    Very simple parser using regex heuristics for vendor, date, amount.
    """
    vendor_match = re.search(r"Vendor:\s*([A-Za-z0-9 .,&'-]+)", text, re.IGNORECASE)
    vendor = vendor_match.group(1).strip() if vendor_match else None

    # Date formats like 2024-05-24 or 05/24/2024
    date_match = re.search(r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})", text)
    parsed_date = None
    if date_match:
        raw = date_match.group(1)
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                parsed_date = datetime.strptime(raw, fmt).date()
                break
            except ValueError:
                continue

    # Amount like USD 123.45 or $123.45
    amount_match = re.search(r"(USD|\$)\s?(\d+(?:\.\d{2})?)", text, re.IGNORECASE)
    currency = None
    amount = None
    if amount_match:
        curr = amount_match.group(1).upper()
        currency = "USD" if curr == "$" else curr
        try:
            amount = float(amount_match.group(2))
        except Exception:
            amount = None

    return {"vendor": vendor, "date": parsed_date, "amount": amount, "currency": currency}


def upsert_extraction(document_id: int, parsed: Dict, raw_text: str):
    """Create or update extraction for a document."""
    ext = Extraction.query.filter_by(document_id=document_id).first()
    if not ext:
        ext = Extraction(document_id=document_id)
        db.session.add(ext)
    ext.vendor = parsed.get("vendor")
    ext.amount = parsed.get("amount")
    ext.currency = parsed.get("currency")
    ext.date = parsed.get("date")
    ext.raw_text = raw_text
    db.session.commit()
    return ext


CATEGORIES = [
    ("Meals", ["restaurant", "cafe", "coffee", "food", "meal"]),
    ("Travel", ["uber", "lyft", "flight", "airlines", "train", "taxi"]),
    ("Supplies", ["office", "stationery", "supply", "paper", "ink"]),
    ("Lodging", ["hotel", "inn", "motel"]),
]


def auto_categorize(vendor: Optional[str], raw_text: Optional[str]) -> Tuple[str, float]:
    """Heuristic categorization based on keywords in vendor/raw_text."""
    text = f"{vendor or ''} {raw_text or ''}".lower()
    for cat, keywords in CATEGORIES:
        for kw in keywords:
            if kw in text:
                return cat, 0.8
    return "Uncategorized", 0.5


def assign_category(document_id: int, category_name: str, confidence: float = 0.8):
    """Create or update a document's category assignment."""
    cat = Category.query.filter_by(name=category_name).first()
    if not cat:
        cat = Category(name=category_name, description=f"Auto-created category {category_name}")
        db.session.add(cat)
        db.session.flush()

    link = DocumentCategory.query.filter_by(document_id=document_id, category_id=cat.id).first()
    if not link:
        link = DocumentCategory(document_id=document_id, category_id=cat.id, confidence=confidence)
        db.session.add(link)
    else:
        link.confidence = max(link.confidence or 0, confidence)
    db.session.commit()
    return link


def log_action(action: str, document_id: Optional[int] = None, user_id: Optional[str] = None, details=None):
    """Log an action for audit purposes."""
    entry = AuditLog(action=action, document_id=document_id, user_id=user_id, details=details)
    db.session.add(entry)
    db.session.commit()
    return entry


def create_job(job_type: str, document_id: Optional[int] = None, version_id: Optional[int] = None, meta=None) -> Job:
    """Create a processing job."""
    job = Job(job_type=job_type, status="queued", document_id=document_id, version_id=version_id, meta=meta)
    db.session.add(job)
    db.session.commit()
    return job


def run_job(job: Job, upload_dir: str):
    """Execute a job synchronously (demo)."""
    job.status = "running"
    job.attempts += 1
    db.session.commit()

    try:
        if job.job_type == "ocr":
            version = DocumentVersion.query.get(job.version_id)
            if not version:
                raise ValueError("Version not found")
            raw_text = naive_ocr_text_from_file(version.storage_path)
            parsed = parse_receipt(raw_text)
            upsert_extraction(version.document_id, parsed, raw_text)
            version.status = "processed"
            db.session.commit()
            # Categorize after OCR
            ext = Extraction.query.filter_by(document_id=version.document_id).first()
            vendor = ext.vendor if ext else None
            text = ext.raw_text if ext else None
            cat_name, conf = auto_categorize(vendor, text)
            assign_category(version.document_id, cat_name, conf)
        elif job.job_type == "categorize":
            ext = Extraction.query.filter_by(document_id=job.document_id).first()
            cat_name, conf = auto_categorize(ext.vendor if ext else None, ext.raw_text if ext else None)
            assign_category(job.document_id, cat_name, conf)
        else:
            raise ValueError(f"Unknown job type {job.job_type}")

        job.status = "done"
        job.last_error = None
        db.session.commit()
    except Exception as exc:
        job.status = "failed"
        job.last_error = str(exc)
        db.session.commit()
        raise
