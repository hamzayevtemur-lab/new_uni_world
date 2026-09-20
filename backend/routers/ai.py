from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from ai.ocr_scanner import scan_document_ai
from ai.sop_evaluator import evaluate_sop_ai
from ai.rag_counselor import answer_counselor_rag

router = APIRouter(prefix="/api/ai", tags=["AI Engineering Features"])


class SOPEvaluateRequest(BaseModel):
    sop_text: str
    target_country: Optional[str] = "General"
    target_major: Optional[str] = "Computer Science"


class AIChatRequest(BaseModel):
    message: str


@router.post("/scan-document")
async def ai_scan_document(file: UploadFile = File(...)):
    """
    [AI Vision & OCR Engine]
    Processes passport scan / IELTS certificate image using Computer Vision & MRZ Regex NER.
    """
    if not file.content_type.startswith("image/") and not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file (JPG, PNG) or PDF.")

    contents = await file.read()
    result = scan_document_ai(contents)
    return result


@router.post("/evaluate-sop")
async def ai_evaluate_sop(data: SOPEvaluateRequest):
    """
    [NLP & Semantic Vector Analysis Engine]
    Evaluates Statement of Purpose / Motivation Letter readability, vocabulary richness,
    and semantic goal alignment against admission criteria.
    """
    if not data.sop_text or not data.sop_text.strip():
        raise HTTPException(status_code=400, detail="Statement of Purpose text cannot be empty.")

    result = evaluate_sop_ai(data.sop_text, data.target_country, data.target_major)
    return result


@router.post("/counselor-chat")
async def ai_counselor_chat(data: AIChatRequest):
    """
    [RAG Vector Architecture AI Counselor]
    Retrieves semantically matched passages from vector knowledge base and synthesizes
    counselor response with source citations.
    """
    if not data.message or not data.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    result = answer_counselor_rag(data.message)
    return result
