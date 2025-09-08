from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy import Index

db = SQLAlchemy()


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Document(db.Model, TimestampMixin):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(128), nullable=False)
    size_bytes = db.Column(db.BigInteger, nullable=False, default=0)
    current_version_id = db.Column(db.Integer, db.ForeignKey("document_versions.id"))

    # Relationships
    versions = db.relationship(
        "DocumentVersion",
        backref="document",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_number.desc()",
    )
    extraction = db.relationship(
        "Extraction",
        backref="document",
        lazy=True,
        uselist=False,
        cascade="all, delete-orphan",
    )
    categories = db.relationship(
        "DocumentCategory",
        backref="document",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def as_dict(self):
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "current_version_id": self.current_version_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DocumentVersion(db.Model, TimestampMixin):
    __tablename__ = "document_versions"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False, default=1)
    storage_path = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="uploaded")  # uploaded, processed, failed
    checksum = db.Column(db.String(64), nullable=True)

    __table_args__ = (
        Index("idx_version_doc_num", "document_id", "version_number", unique=True),
    )

    def as_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "version_number": self.version_number,
            "storage_path": self.storage_path,
            "status": self.status,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Extraction(db.Model, TimestampMixin):
    __tablename__ = "extractions"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False, unique=True)
    vendor = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(8), nullable=True)
    date = db.Column(db.Date, nullable=True)
    raw_text = db.Column(db.Text, nullable=True)
    extra = db.Column(MySQLJSON, nullable=True)

    def as_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "vendor": self.vendor,
            "amount": self.amount,
            "currency": self.currency,
            "date": self.date.isoformat() if self.date else None,
            "raw_text": self.raw_text,
            "extra": self.extra,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.String(255), nullable=True)


class DocumentCategory(db.Model, TimestampMixin):
    __tablename__ = "document_categories"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    confidence = db.Column(db.Float, nullable=True)

    category = db.relationship("Category")

    __table_args__ = (
        Index("idx_doc_category_unique", "document_id", "category_id", unique=True),
    )

    def as_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "category": {
                "id": self.category.id,
                "name": self.category.name,
                "description": self.category.description,
            }
            if self.category
            else None,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Job(db.Model, TimestampMixin):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(64), nullable=False)  # ocr, categorize
    status = db.Column(db.String(32), nullable=False, default="queued")  # queued, running, done, failed
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
    version_id = db.Column(db.Integer, db.ForeignKey("document_versions.id"), nullable=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.Text, nullable=True)
    meta = db.Column(MySQLJSON, nullable=True)

    def as_dict(self):
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status,
            "document_id": self.document_id,
            "version_id": self.version_id,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "meta": self.meta,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AuditLog(db.Model, TimestampMixin):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(64), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
    user_id = db.Column(db.String(64), nullable=True)  # Placeholder for future auth integration
    details = db.Column(MySQLJSON, nullable=True)

    def as_dict(self):
        return {
            "id": self.id,
            "action": self.action,
            "document_id": self.document_id,
            "user_id": self.user_id,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
