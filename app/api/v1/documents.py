from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...models.document import Document
from ...models.user import User
from ...schemas.response import ResponseModel
from ...core.deps import get_current_user
from ...config import settings
import os
import uuid
from datetime import datetime
from pathlib import Path

router = APIRouter()

ALLOWED_EXTENSIONS = set(settings.ALLOWED_EXTENSIONS.split(","))

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@router.post("/upload", response_model=ResponseModel)
async def upload_document(
    document_type: str,
    user_id: Optional[str] = None,
    truck_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    booking_id: Optional[str] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a document"""
    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {settings.ALLOWED_EXTENSIONS}"
        )
    
    # Check file size
    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE} bytes"
        )
    
    # Generate unique filename
    file_ext = file.filename.rsplit(".", 1)[1].lower()
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    
    # Create directory structure
    upload_dir = Path(settings.UPLOAD_DIR) / document_type
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = upload_dir / unique_filename
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Create document record
    document = Document(
        user_id=user_id or current_user.id,
        truck_id=truck_id,
        driver_id=driver_id,
        booking_id=booking_id,
        document_type=document_type,
        document_name=file.filename,
        file_path=str(file_path),
        file_size=len(file_content),
        mime_type=file.content_type
    )
    
    db.add(document)
    db.commit()
    db.refresh(document)
    
    return ResponseModel(
        success=True,
        message="Document uploaded successfully",
        data={"document_id": document.id, "file_path": document.file_path}
    )

@router.get("/", response_model=ResponseModel)
async def get_documents(
    user_id: Optional[str] = None,
    truck_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    booking_id: Optional[str] = None,
    document_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get documents with filters"""
    from ...utils.pagination import paginate_query, create_paginated_response
    
    query = db.query(Document)
    
    if user_id:
        query = query.filter(Document.user_id == user_id)
    if truck_id:
        query = query.filter(Document.truck_id == truck_id)
    if driver_id:
        query = query.filter(Document.driver_id == driver_id)
    if booking_id:
        query = query.filter(Document.booking_id == booking_id)
    if document_type:
        query = query.filter(Document.document_type == document_type)
    
    paginated_query, pagination_info = paginate_query(query, page, page_size)
    documents = paginated_query.all()
    
    return ResponseModel(
        success=True,
        data=create_paginated_response(
            [{"id": d.id, "document_type": d.document_type, "document_name": d.document_name,
              "verification_status": d.verification_status, "created_at": d.created_at.isoformat()}
             for d in documents],
            pagination_info["total"],
            pagination_info["page"],
            pagination_info["page_size"]
        ).model_dump()
    )

@router.put("/{document_id}/verify", response_model=ResponseModel)
async def verify_document(
    document_id: str,
    status: str,  # 'verified' or 'rejected'
    rejection_reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verify or reject a document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if status not in ["verified", "rejected"]:
        raise HTTPException(status_code=400, detail="Status must be 'verified' or 'rejected'")
    
    document.verification_status = status
    document.verified_by = current_user.id
    document.verified_at = datetime.utcnow()
    
    if status == "rejected" and rejection_reason:
        document.rejection_reason = rejection_reason
    
    db.commit()
    
    return ResponseModel(success=True, message=f"Document {status} successfully")

@router.delete("/{document_id}", response_model=ResponseModel)
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a document"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check permission
    if document.user_id != current_user.id and current_user.user_type not in ["cfs_admin", "security_officer"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")
    
    # Delete file
    if os.path.exists(document.file_path):
        os.remove(document.file_path)
    
    db.delete(document)
    db.commit()
    
    return ResponseModel(success=True, message="Document deleted successfully")
