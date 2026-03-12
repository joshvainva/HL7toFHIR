from fastapi import APIRouter, Request, File, UploadFile, Form, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from typing import List, Optional
import json
import io

from app.hl7_parser.parser import parse_hl7_messages
from app.exporter import json_to_xml, generate_pdf

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.post("/convert")
async def convert_hl7(
    hl7_text: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    messages = []
    
    # Process manual text input (can be multiple messages separated by blank lines or multiple segments)
    if hl7_text and hl7_text.strip():
        # A simple approach: split by MSH segment to handle multiple messages
        split_msgs = ["MSH|" + m for m in hl7_text.split("MSH|") if m.strip()]
        if not split_msgs: # Fallback if text doesn't contain MSH but is a single message
            split_msgs = [hl7_text]
        messages.extend(split_msgs)
        
    # Process file uploads
    if files:
        for file in files:
            if file.filename:
                content = await file.read()
                content_str = content.decode('utf-8')
                split_msgs = ["MSH|" + m for m in content_str.split("MSH|") if m.strip()]
                if not split_msgs:
                    split_msgs = [content_str]
                messages.extend(split_msgs)

    if not messages:
        return {"error": "No valid HL7 messages found."}

    # Process all messages and collect results
    results = parse_hl7_messages(messages)
    
    # Enrich with XML
    for res in results:
        if res.get("status") == "success" and "fhir" in res:
            res["xml"] = json_to_xml(res["fhir"])
    
    return {"results": results}

@router.post("/export/pdf")
async def export_pdf(payload: str = Form(...)):
    bundle_json = json.loads(payload)
    pdf_bytes = generate_pdf(bundle_json)
    
    # Use io.BytesIO to stream the bytes and avoid encoding issues
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=fhir_conversion.pdf"}
    )

@router.post("/export/json")
async def export_json(payload: str = Form(...)):
    data = json.loads(payload)
    json_str = json.dumps(data, indent=2)
    return Response(
        content=json_str,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=fhir_conversion.json"}
    )

@router.post("/export/xml")
async def export_xml(payload: str = Form(...)):
    data = json.loads(payload)
    xml_content = ""
    if isinstance(data, dict) and "results" in data:
        xml_content = "\n\n".join([r.get("xml", "") for r in data.get("results", [])])
    else:
        xml_content = data.get("xml", "")
        
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=fhir_conversion.xml"}
    )
