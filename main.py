import os
import uuid

from PyPDF2 import PdfReader
from docx2pdf import convert
from fastapi import FastAPI, File, UploadFile, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.staticfiles import StaticFiles

app = FastAPI()

# Define the server URL
SERVER_URL = "http://0.0.0.0:8000"

# Upload directory
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Set up Jinja2 templates for rendering HTML
templates = Jinja2Templates(directory="templates")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# In-memory storage for file data
file_data = {}
current_file_id = None  # Track the current file being processed
force_print_requested = {}


class ShreddedPagesUpdate(BaseModel):
    shredded_pages: int


class ForcePrintRequest(BaseModel):
    file_id: str


def count_pdf_pages(file_path):
    """Count pages in a PDF file."""
    try:
        reader = PdfReader(file_path)
        return len(reader.pages)
    except Exception:
        return 0


@app.get("/", response_class=HTMLResponse)
async def upload_page(request: Request):
    """Render the file upload page."""
    return templates.TemplateResponse("index.html", {"request": request, "files": file_data})


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


@app.get("/check_force_print/{file_id}")
async def check_force_print(file_id: str):
    """ESP32 checks if force print was triggered."""
    if force_print_requested.get(file_id):
        shredded_pages = file_data[file_id]["shredded_pages"]
        pages_to_print = shredded_pages // 3
        return {"force_print": True, "pages_to_print": pages_to_print}
    return {"force_print": False}


@app.post("/force_print/")
async def force_print(file_id: str = Form(...)):
    """User triggers force print via web UI."""
    if file_id not in file_data:
        raise HTTPException(status_code=404, detail="File not found")

    force_print_requested[file_id] = True
    return RedirectResponse(url="/", status_code=303)


@app.get("/cancel_print/{file_id}")
async def cancel_print(file_id: str):
    """User cancels print job via web UI."""
    global current_file_id
    if file_id == current_file_id:
        current_file_id = None
    return RedirectResponse(url="/", status_code=303)
