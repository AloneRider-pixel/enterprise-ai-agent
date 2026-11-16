"""
Document management API routes.
Handles document upload, ingestion, and lifecycle management.
"""
import hashlib
import logging
import shutil
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.database import get_db, vector_store
from app.models.database import Document
from app.models.schemas import DocumentListItem, DocumentStatus, DocumentUploadResponse
from app.rag.chunking import text_chunker
from app.rag.embeddings import embedding_service
from app.rag.pdf_parser import (
    PDFParseError,
    pages_to_segments,
    parse_pdf,
    render_page_images,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])
MAX_FILE_SIZE = 50 * 1024 * 1024

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/markdown": "md",
}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document for processing.
    Supports PDF, TXT, DOCX, and Markdown files.
    """
    # Validate file type
    content_type = file.content_type
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {content_type}. Allowed: {list(ALLOWED_TYPES.keys())}",
        )
    
    # Read file content
    content = await file.read(MAX_FILE_SIZE + 1)
    file_size = len(content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 50MB.",
        )
    
    # Compute content hash for deduplication
    content_hash = hashlib.sha256(content).hexdigest()
    
    # Check for duplicate
    user_id = uuid.UUID(current_user["user_id"])
    result = await db.execute(
        select(Document).where(
            Document.content_hash == content_hash,
            Document.uploaded_by == user_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document already exists: {existing.filename} (ID: {existing.id})",
        )
    
    # Extract text content
    file_type = ALLOWED_TYPES[content_type]
    text_content = _extract_text(content, file_type)

    # Multimodal PDF pass: page-aware text/table/image segments for
    # ingestion plus rendered page screenshots for checkable citations.
    doc_id = uuid.uuid4()
    pdf_metadata = {}
    if file_type == "pdf":
        pdf_metadata = _build_pdf_metadata(content, str(doc_id))
        if len((text_content or "").strip()) < 50 and pdf_metadata.get("pdf_segments"):
            # Scanned or screenshot PDF: the readable content comes from the
            # page-aware segments (tables, OCR, image descriptions).
            text_content = "\n\n".join(
                segment["content"] for segment in pdf_metadata["pdf_segments"]
            )

    if not text_content or len(text_content.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract meaningful text from the file.",
        )

    # Create document record
    document = Document(
        id=doc_id,
        filename=file.filename or "unknown",
        file_type=file_type,
        file_size=file_size,
        content_hash=content_hash,
        status="uploaded",
        raw_content=text_content,
        uploaded_by=user_id,
        doc_metadata=pdf_metadata,
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    logger.info(f"Document uploaded: {file.filename} ({file_size} bytes)")
    
    return DocumentUploadResponse(
        document_id=str(document.id),
        filename=document.filename,
        size_bytes=file_size,
        status=document.status,
        created_at=document.created_at,
    )


@router.post("/ingest/{document_id}")
async def ingest_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger document ingestion (chunking + embedding + vector storage).
    """
    # Get document owned by the authenticated user
    try:
        document_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    user_id = uuid.UUID(current_user["user_id"])
    result = await db.execute(
        select(Document).where(
            Document.id == document_uuid,
            Document.uploaded_by == user_id,
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.status == "indexed":
        return {"status": "already_indexed", "chunks": document.chunk_count}
    
    # Update status to processing
    document.status = "processing"
    await db.commit()
    
    try:
        base_metadata = {
            "document_id": str(document.id),
            "filename": document.filename,
            "file_type": document.file_type,
        }
        chunks = _chunk_document(document, base_metadata)

        if not chunks:
            document.status = "failed"
            await db.commit()
            return {"status": "failed", "error": "No chunks generated"}
        
        # Generate embeddings in batch
        texts = [chunk["content"] for chunk in chunks]
        embeddings = await embedding_service.embed_batch(texts)
        
        # Store in pgvector
        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            await vector_store.store_embedding(
                chunk_id=chunk["chunk_id"],
                document_id=str(document.id),
                content=chunk["content"],
                embedding=embedding,
                metadata=chunk["metadata"],
                chunk_index=chunk.get("chunk_index", index),
            )
        
        # Update document status
        document.status = "indexed"
        document.chunk_count = len(chunks)
        document.indexed_at = datetime.utcnow()
        await db.commit()
        
        logger.info(f"Document indexed: {document.filename} -> {len(chunks)} chunks")
        
        return {
            "status": "indexed",
            "document_id": str(document.id),
            "chunks": len(chunks),
            "total_tokens": sum(c["metadata"].get("token_count", 0) for c in chunks),
        }
    
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        document.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("", response_model=DocumentListItem)
async def list_documents(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded documents with their status."""
    user_id = uuid.UUID(current_user["user_id"])
    result = await db.execute(
        select(Document)
        .where(Document.uploaded_by == user_id)
        .order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    
    items = [
        DocumentStatus(
            document_id=str(doc.id),
            filename=doc.filename,
            status=doc.status,
            chunk_count=doc.chunk_count,
            created_at=doc.created_at,
            indexed_at=doc.indexed_at,
        )
        for doc in documents
    ]
    
    return DocumentListItem(documents=items, total=len(items))


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and its associated chunks."""
    try:
        document_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    user_id = uuid.UUID(current_user["user_id"])
    result = await db.execute(
        select(Document).where(
            Document.id == document_uuid,
            Document.uploaded_by == user_id,
        )
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    await vector_store.delete_document_chunks(document_id)
    await db.delete(document)
    await db.commit()

    # Remove rendered page images, if any.
    shutil.rmtree(
        Path(settings.page_image_dir) / str(document.id), ignore_errors=True
    )

    logger.info(f"Document deleted: {document.filename}")
    return {"status": "deleted", "document_id": document_id}


@router.get("/{document_id}/pages/{page_number}/image")
async def get_page_image(
    document_id: str,
    page_number: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Serve the rendered screenshot of one PDF page.
    Lets a user open the original page behind a citation to check the evidence.
    """
    try:
        document_uuid = uuid.UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    if page_number < 1:
        raise HTTPException(status_code=400, detail="Invalid page number")

    user_id = uuid.UUID(current_user["user_id"])
    result = await db.execute(
        select(Document).where(
            Document.id == document_uuid,
            Document.uploaded_by == user_id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Resolve and check containment before touching the filesystem. UUID/int
    # validation alone does not protect against symlinks in the image cache.
    image_root = Path(settings.page_image_dir).resolve()
    image_path = (
        image_root / str(document.id) / f"page-{page_number}.png"
    ).resolve()
    if not image_path.is_relative_to(image_root):
        raise HTTPException(status_code=404, detail="Page image not found")
    if not image_path.is_file():
        raise HTTPException(status_code=404, detail="Page image not found")

    return FileResponse(image_path, media_type="image/png")


def _build_pdf_metadata(content: bytes, document_id: str) -> dict:
    """
    Parse a PDF into page-aware segments and render page screenshots.
    Falls back to an empty page structure so flat-text ingestion still works
    when the page-aware parse fails.
    """
    try:
        parsed = parse_pdf(content)
    except PDFParseError as e:
        logger.warning(f"Page-aware PDF parse failed, flat text only: {e}")
        return {}

    rendered_pages = []
    try:
        rendered = render_page_images(
            content,
            document_id,
            settings.page_image_dir,
            max_pages=settings.max_render_pages,
        )
        rendered_pages = sorted(rendered.keys())
    except PDFParseError as e:
        logger.warning(f"PDF page rendering failed: {e}")

    return {
        "page_count": parsed.page_count,
        "rendered_pages": rendered_pages,
        "pdf_segments": pages_to_segments(parsed),
    }


def _chunk_document(document: Document, base_metadata: dict) -> list:
    """
    Chunk a document for ingestion. PDFs parsed into page-aware segments keep
    their page number and kind (text/table) on every chunk; other files use
    the flat raw text.
    """
    segments = (document.doc_metadata or {}).get("pdf_segments") or []

    if not segments:
        return text_chunker.chunk_text(document.raw_content, metadata=base_metadata)

    chunks = []
    for segment in segments:
        chunks.extend(
            text_chunker.chunk_text(
                segment["content"],
                metadata={
                    **base_metadata,
                    "page_number": segment["page_number"],
                    "kind": segment["kind"],
                },
            )
        )
    # Renumber across segments: the chunker restarts its index per segment.
    for index, chunk in enumerate(chunks):
        chunk["chunk_index"] = index
        chunk["metadata"]["chunk_index"] = index
        chunk["metadata"]["chunk_total"] = len(chunks)
    return chunks


def _extract_text(content: bytes, file_type: str) -> str:
    """Extract text content from uploaded file."""
    if file_type == "txt" or file_type == "md":
        return content.decode("utf-8", errors="ignore")
    
    elif file_type == "pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(content))
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""
    
    elif file_type == "docx":
        try:
            from docx import Document as DocxDocument
            doc = DocxDocument(BytesIO(content))
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            return ""
    
    return ""
