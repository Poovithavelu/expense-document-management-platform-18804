import math
import mimetypes
import os
from datetime import datetime
from flask import current_app, request, send_file
from flask.views import MethodView
from flask_smorest import Blueprint, abort

from ..models import db, Document, DocumentVersion, Extraction, DocumentCategory, Job
from ..schemas import (
    DocumentSchema,
    DocumentCreateResponseSchema,
    ExtractionSchema,
    DocumentCategorySchema,
    JobSchema,
    SearchResultSchema,
    PaginationSchema,
)
from ..services import (
    save_file,
    create_job,
    run_job,
    log_action,
)

blp = Blueprint(
    "Receipt API",
    "receipt_api",
    url_prefix="/api",
    description="Endpoints for uploading, processing, managing documents and admin."
)


# PUBLIC_INTERFACE
@blp.route("/upload")
class UploadAPI(MethodView):
    """Upload files to create a new document and its first version."""
    @blp.response(201, DocumentCreateResponseSchema)
    def post(self):
        """
        Upload a document file (PDF/Image).
        Returns created document and version info, and queues OCR job.
        """
        if "file" not in request.files:
            abort(400, message="Missing file field")

        f = request.files["file"]
        if f.filename == "":
            abort(400, message="Empty filename")

        mime_type = f.mimetype or (mimetypes.guess_type(f.filename)[0] or "application/octet-stream")
        size = request.content_length or 0

        doc = Document(original_filename=f.filename, mime_type=mime_type, size_bytes=size)
        db.session.add(doc)
        db.session.flush()

        # Version 1
        version_number = 1
        storage_path, checksum = save_file(current_app.config["UPLOAD_DIR"], doc.id, version_number, f.filename, f.stream)
        version = DocumentVersion(
            document_id=doc.id,
            version_number=version_number,
            storage_path=storage_path,
            status="uploaded",
            checksum=checksum,
        )
        db.session.add(version)
        db.session.flush()

        doc.current_version_id = version.id
        db.session.commit()

        # Queue and run OCR job synchronously for demo
        job = create_job("ocr", document_id=doc.id, version_id=version.id, meta={"filename": f.filename})
        try:
            run_job(job, current_app.config["UPLOAD_DIR"])
        except Exception:
            current_app.logger.exception("OCR job failed")
        log_action("upload", document_id=doc.id, details={"filename": f.filename})

        return {"document": doc.as_dict(), "version": version.as_dict()}


# PUBLIC_INTERFACE
@blp.route("/documents")
class DocumentsAPI(MethodView):
    """List and create documents (creation via upload)."""
    @blp.response(200, {"application/json": {"schema": DocumentSchema(many=True)}})
    def get(self):
        """
        List documents with basic pagination.
        Query params: page, page_size
        """
        page = int(request.args.get("page", 1))
        page_size = min(int(request.args.get("page_size", 20)), 100)
        q = Document.query.order_by(Document.created_at.desc())
        items = q.offset((page - 1) * page_size).limit(page_size).all()
        resp = [d.as_dict() for d in items]
        return resp


# PUBLIC_INTERFACE
@blp.route("/documents/<int:document_id>")
class DocumentDetailAPI(MethodView):
    """Retrieve a single document."""
    @blp.response(200, DocumentSchema)
    def get(self, document_id: int):
        """
        Get document by ID.
        """
        doc = Document.query.get_or_404(document_id)
        return doc.as_dict()


# PUBLIC_INTERFACE
@blp.route("/documents/<int:document_id>/download")
class DocumentDownloadAPI(MethodView):
    """Download the current version file of a document."""
    def get(self, document_id: int):
        doc = Document.query.get_or_404(document_id)
        if not doc.current_version_id:
            abort(404, message="No version available")
        version = DocumentVersion.query.get(doc.current_version_id)
        if not version or not os.path.exists(version.storage_path):
            abort(404, message="File not found")
        return send_file(version.storage_path, as_attachment=True, download_name=os.path.basename(version.storage_path))


# PUBLIC_INTERFACE
@blp.route("/documents/<int:document_id>/versions")
class DocumentVersionsAPI(MethodView):
    """Manage document versions."""
    @blp.response(200, {"application/json": {"schema": DocumentSchema}})
    def get(self, document_id: int):
        """
        List versions for a document.
        """
        doc = Document.query.get_or_404(document_id)
        versions = [v.as_dict() for v in doc.versions]
        return {"document": doc.as_dict(), "versions": versions}

    @blp.response(201, {"application/json": {"schema": DocumentCreateResponseSchema}})
    def post(self, document_id: int):
        """
        Upload a new version for an existing document.
        """
        doc = Document.query.get_or_404(document_id)
        if "file" not in request.files:
            abort(400, message="Missing file field")
        f = request.files["file"]
        if f.filename == "":
            abort(400, message="Empty filename")

        version_number = (doc.versions[0].version_number + 1) if doc.versions else 1
        storage_path, checksum = save_file(current_app.config["UPLOAD_DIR"], doc.id, version_number, f.filename, f.stream)
        version = DocumentVersion(
            document_id=doc.id,
            version_number=version_number,
            storage_path=storage_path,
            status="uploaded",
            checksum=checksum,
        )
        db.session.add(version)
        db.session.flush()
        doc.current_version_id = version.id
        db.session.commit()

        job = create_job("ocr", document_id=doc.id, version_id=version.id, meta={"filename": f.filename})
        try:
            run_job(job, current_app.config["UPLOAD_DIR"])
        except Exception:
            current_app.logger.exception("OCR job failed on new version")

        log_action("upload_version", document_id=doc.id, details={"filename": f.filename, "version_number": version_number})
        return {"document": doc.as_dict(), "version": version.as_dict()}


# PUBLIC_INTERFACE
@blp.route("/documents/<int:document_id>/extraction")
class ExtractionAPI(MethodView):
    """Retrieve extraction for a document."""
    @blp.response(200, ExtractionSchema)
    def get(self, document_id: int):
        """
        Get extracted fields for a document.
        """
        ext = Extraction.query.filter_by(document_id=document_id).first()
        if not ext:
            abort(404, message="No extraction available. Trigger OCR first.")
        return ext.as_dict()


# PUBLIC_INTERFACE
@blp.route("/documents/<int:document_id>/categories")
class CategoriesAPI(MethodView):
    """List categories for a document."""
    @blp.response(200, {"application/json": {"schema": DocumentCategorySchema(many=True)}})
    def get(self, document_id: int):
        cats = DocumentCategory.query.filter_by(document_id=document_id).all()
        return [c.as_dict() for c in cats]


# PUBLIC_INTERFACE
@blp.route("/search")
class SearchAPI(MethodView):
    """Search documents by vendor, amount, date."""
    @blp.response(200, SearchResultSchema)
    def get(self):
        """
        Search across extracted fields.
        Query: q (text), vendor, min_amount, max_amount, date_from, date_to, page, page_size
        """
        q = request.args.get("q")
        vendor = request.args.get("vendor")
        min_amount = request.args.get("min_amount", type=float)
        max_amount = request.args.get("max_amount", type=float)
        date_from = request.args.get("date_from")
        date_to = request.args.get("date_to")
        page = request.args.get("page", type=int, default=1)
        page_size = min(request.args.get("page_size", type=int, default=20), 100)

        query = Document.query
        if any([q, vendor, min_amount is not None, max_amount is not None, date_from, date_to]):
            query = query.join(Extraction, Extraction.document_id == Document.id)

        if q:
            like = f"%{q}%"
            query = query.filter((Extraction.vendor.ilike(like)) | (Extraction.raw_text.ilike(like)))
        if vendor:
            query = query.filter(Extraction.vendor.ilike(f"%{vendor}%"))
        if min_amount is not None:
            query = query.filter(Extraction.amount >= min_amount)
        if max_amount is not None:
            query = query.filter(Extraction.amount <= max_amount)
        if date_from:
            try:
                df = datetime.fromisoformat(date_from).date()
                query = query.filter(Extraction.date >= df)
            except Exception:
                abort(400, message="Invalid date_from format, use YYYY-MM-DD")
        if date_to:
            try:
                dt = datetime.fromisoformat(date_to).date()
                query = query.filter(Extraction.date <= dt)
            except Exception:
                abort(400, message="Invalid date_to format, use YYYY-MM-DD")

        total = query.count()
        items = query.order_by(Document.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        docs = [d.as_dict() for d in items]
        return {"documents": docs, "total": total, "page": page, "page_size": page_size}


# PUBLIC_INTERFACE
@blp.route("/admin/jobs")
class AdminJobsAPI(MethodView):
    """List recent jobs with status."""
    @blp.response(200, {"application/json": {"schema": JobSchema(many=True)}})
    def get(self):
        """
        Get last 100 jobs.
        """
        jobs = Job.query.order_by(Job.created_at.desc()).limit(100).all()
        return [j.as_dict() for j in jobs]


# PUBLIC_INTERFACE
@blp.route("/admin/stats")
class AdminStatsAPI(MethodView):
    """Basic statistics over documents and processing."""
    @blp.response(200, {"application/json": {"schema": PaginationSchema}})
    def get(self):
        """
        Return counts and simple metrics.
        """
        doc_count = Document.query.count()
        ext_count = Extraction.query.count()
        jobs_running = Job.query.filter_by(status="running").count()
        jobs_failed = Job.query.filter_by(status="failed").count()
        jobs_done = Job.query.filter_by(status="done").count()

        return {
            "total": doc_count,
            "total_pages": int(math.ceil(doc_count / 20)) if doc_count else 0,
            "page": 1,
            "page_size": 20,
            "jobs_running": jobs_running,
            "jobs_failed": jobs_failed,
            "jobs_done": jobs_done,
            "extractions": ext_count,
        }
