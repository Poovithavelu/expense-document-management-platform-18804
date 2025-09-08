# Expense Document Management Platform - Backend

This repository contains the Flask backend for uploading, processing (OCR), categorizing, and managing documents/receipts, with MySQL persistence and OpenAPI docs (via flask-smorest).

Quick start:
1) Create a .env based on receipt_processing_backend/.env.example with correct MySQL credentials (see document_database container).
2) Install requirements
3) Run the API

Environment variables (provided via .env):
- MYSQL_URL, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB, MYSQL_PORT
- UPLOAD_DIR (optional; defaults to instance/uploads)

Endpoints overview:
- GET /           -> health check
- POST /api/upload -> upload a document file
- GET /api/documents -> list documents
- GET /api/documents/{id} -> get document
- GET /api/documents/{id}/download -> download current version file
- GET /api/documents/{id}/versions -> list versions
- POST /api/documents/{id}/versions -> upload new version
- GET /api/documents/{id}/extraction -> get OCR-extracted fields
- GET /api/documents/{id}/categories -> get categories
- GET /api/search -> search by vendor/amount/date/free-text
- GET /api/admin/jobs -> job list
- GET /api/admin/stats -> statistics

OpenAPI docs: /docs