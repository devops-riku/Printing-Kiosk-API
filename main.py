import os
import shutil
import uuid

import uvicorn
from PyPDF2 import PdfReader
from docx2pdf import convert
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, Request, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

load_dotenv()

app = FastAPI()

# Define the server URL
SERVER_URL = os.getenv('HOST')

# Upload directory
UPLOAD_DIR = "uploads"
STATIC_DIR = "static"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Set up Jinja2 templates for rendering HTML
templates = Jinja2Templates(directory="templates")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

file_data = {}
current_file_id = None


class ShreddedPagesUpdate(BaseModel):
    shredded_pages: int


class PrinterSelection(BaseModel):
    printer: str


def count_pdf_pages(file_path):
    """Count pages in a PDF file."""
    try:
        reader = PdfReader(file_path)
        return len(reader.pages)
    except Exception:
        return 0


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page with the current file's progress."""
    global current_file_id
    shutil.rmtree(UPLOAD_DIR)
    os.makedirs(UPLOAD_DIR)

    file_data.clear()
    current_file_id = None
    return templates.TemplateResponse("landing.html", {"request": request})


@app.get("/scan-to-upload")
async def scan_qr_code(request: Request):
    """Redirect to the QR code scanning page."""
    return templates.TemplateResponse("scan-to-upload.html", {"request": request, "host": SERVER_URL})


@app.get("/upload-file", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Render the file upload page."""
    return templates.TemplateResponse("upload-file.html", {"request": request, "files": file_data})


@app.get("/progress")
async def progress(request: Request):
    """Render the progress page with the current file's progress."""
    return templates.TemplateResponse("progress.html", {"request": request, "current_file_id": current_file_id})


@app.post("/upload/")
async def upload_file(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """Upload PDF or DOCX files, convert DOCX to PDF, and count pages."""
    global current_file_id
    if current_file_id is not None:
        return {"error": "A file is already being processed. Please wait until it is shredded and printed."}

    if not file.filename.endswith((".pdf", ".docx")):
        return {"error": "Only PDF and DOCX files are supported"}

    # Generate a unique ID for the file
    unique_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{unique_id}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Convert DOCX to PDF if necessary
    if file.filename.endswith(".docx"):
        pdf_path = file_path.replace(".docx", ".pdf")
        convert(file_path, pdf_path)
        page_count = count_pdf_pages(pdf_path)
        file_path = pdf_path
        os.remove(file_path.replace(".pdf", ".docx"))  # Remove DOCX
    else:
        page_count = count_pdf_pages(file_path)

    required_shredded_pages = page_count * 3

    file_data[unique_id] = {
        "file_name": file.filename,
        "file_path": file_path,
        "required_shredded_pages": required_shredded_pages,
        "shredded_pages": 0
    }

    current_file_id = unique_id
    return {
        "file_id": unique_id,
        "required_shredded_pages": required_shredded_pages,
        "message": "File uploaded successfully"
    }


@app.get("/check_for_file")
async def check_for_file():
    """Check if a file is available for processing."""
    global current_file_id
    if current_file_id is None:
        return {"message": "No file is currently being processed"}

    file_info = file_data.get(current_file_id)
    if file_info:
        return {
            "file_id": current_file_id,
            "file_url": f"{SERVER_URL}/uploads/{current_file_id}.pdf",
            "required_shredded_pages": file_info["required_shredded_pages"],
            "shredded_pages": file_info["shredded_pages"]
        }
    return {"message": "File data not found"}


@app.post("/update_shredded_pages/{file_id}")
async def update_shredded_pages(file_id: str, update: ShreddedPagesUpdate):
    """Update shredded pages count."""
    if file_id not in file_data:
        raise HTTPException(status_code=404, detail="File not found")

    file_data[file_id]["shredded_pages"] = update.shredded_pages
    return {"message": "Updated shredded pages"}


@app.get("/cancel_print")
async def cancel_print():
    """User cancels print job via web UI and deletes the uploaded file."""
    global current_file_id
    shutil.rmtree(UPLOAD_DIR)
    os.makedirs(UPLOAD_DIR)

    file_data.clear()
    current_file_id = None

    return RedirectResponse(url="/", status_code=303)


@app.get("/clear-current-file")
async def clear_current_file():
    global current_file_id

    current_file_id = None
    return {'message': 'Current file cleared successfully'}


@app.get('/success-page')
async def success_page(request: Request):
    return templates.TemplateResponse("success.html", {"request": request})


@app.get("/current_file_id")
async def get_current_file_id():
    return {"current_file_id": current_file_id}


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)
