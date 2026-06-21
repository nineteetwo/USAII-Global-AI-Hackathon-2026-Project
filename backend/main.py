from fastapi.responses import JSONResponse
import database
import os
import shutil
import time
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
from typing import Optional
from pydantic import BaseModel
from database import get_db, User, ChatMessage
from rag import generate_rag_response
from parse_process.doc_parser import parse_document, clean_text
from parse_process.process_parse import extract, build_backend
from parse_process.guidance_generator import generate_guidance, format_guidance_markdown
from parse_process.process_parse import build_backend
from parse_process.deadline_tracker import build_deadline_report
from parse_process.fpl_calculator import enrich_profile_with_fpl, calculate_fpl_snapshot
from parse_process.caseworker_notes import build_case_note
import json

app = FastAPI(title="CalHelpr Backend")

Base = declarative_base()
database.init_db()

# Local file frontend access configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows browser local files to reach the ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory configuration for user uploaded files
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BACKEND_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Request Data Validations ---
class UserSignup(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: str
    password: str = Field(..., min_length=4)

class UserLogin(BaseModel):
    email: str
    password: str

class ChatInput(BaseModel):
    text: str
    email: Optional[str] = None 
    thread_id: Optional[str] = None
    uploaded_file_path: Optional[str] = "" 

class TrackerStatusUpdate(BaseModel):
    email: str
    thread_id: str
    program_name: str
    status: str  # "applied", "accepted", "rejected"

# --- Endpoints ---
@app.post("/api/signup", status_code=status.HTTP_201_CREATED)
def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """Registers a new user account in the system."""
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    
    new_user = User(name=user_data.name, email=user_data.email, password=user_data.password)
    db.add(new_user)
    db.commit()
    
    return {"message": "Account registered successfully!", "email": new_user.email}

@app.post("/api/login")
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticates a user attempting to sign in."""
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or user.password != user_data.password:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    return {"message": "Access granted", "email": user.email, "name": user.name}

@app.post("/api/chat")
def handle_chat_query(payload: ChatInput, db: Session = Depends(get_db)):
    try:
        # Use existing thread or fallback safely
        assigned_thread_id = payload.thread_id if payload.thread_id else f"thread_{int(time.time())}"

        # Gather all past logs in this thread to analyze state context
        history_records = (
            db.query(ChatMessage)
            .filter(ChatMessage.thread_id == assigned_thread_id)
            .order_by(ChatMessage.id.asc())
            .all()
        )

        has_unhandled_rejection = False
        rejected_program_name = ""
        conversations_list = []

        for msg in history_records:
            # Look for the tracker seed token we dropped in Step 2
            if "[System Event: Application Rejected from" in msg.user_query:
                has_unhandled_rejection = True
                try:
                    rejected_program_name = msg.user_query.split("from ")[1].replace("]", "")
                except Exception:
                    rejected_program_name = "the evaluated program"
            
            conversations_list.append(f"User: {msg.user_query}\nAI: {msg.ai_response}")

        # ROUTE A: Post-Rejection Community Guidance Web Scraping
        if has_unhandled_rejection:
            print(f"[Engine] Found rejection marker for {rejected_program_name}. Launching fallback resource finder...")
            
            local_slm = build_backend(
                backend_name=None, host=None, model=None, 
                temperature=0.3, max_tokens=1024, timeout=300, quiet=True
            )
            
            # Combine chat records into text representations
            conversation_history_string = "\n".join(conversations_list)

            # Fire your guidance module's web search scraping pipeline
            guidance_data = generate_guidance(
                program_applied_to=rejected_program_name,
                application_result="rejected",
                previous_chat_profile=conversation_history_string or "Applicant looking for mutual aid resources.",
                conversations=conversations_list,
                location="CA",
                backend=local_slm,
                enable_web_search=True, # ◄ Kicks off the local scraping system context
                max_resources=4
            )
            
            guidance_markdown = format_guidance_markdown(guidance_data)
            
            # Save this execution step to the permanent chat logs
            new_chat_log = ChatMessage(
                user_email=payload.email,
                thread_id=assigned_thread_id,
                user_query=payload.text,
                ai_response=guidance_markdown
            )
            db.add(new_chat_log)
            db.commit()

            return {
                "response": guidance_markdown,
                "thread_id": assigned_thread_id,
                "id": new_chat_log.id
            }

        # ROUTE B: Standard Document Verification / Eligibility Check (Default)
        print("[Engine] Routing interaction to standard RAG pipeline...")
        eligibility_report = generate_rag_response(
            current_query=payload.text,
            full_history="\n".join(conversations_list),
            user_doc_path=payload.uploaded_file_path or ""
        )

        new_chat_log = ChatMessage(
            user_email=payload.email,
            thread_id=assigned_thread_id,
            user_query=payload.text,
            ai_response=eligibility_report
        )
        db.add(new_chat_log)
        db.commit()

        return {
            "response": eligibility_report,
            "thread_id": assigned_thread_id,
            "id": new_chat_log.id
        }

    except Exception as e:
        print(f"[CRITICAL ERROR] Chat endpoint crashed: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal Server error: {str(e)}"}
        )

@app.get("/api/history")
def get_user_history_logs(email: Optional[str] = None, db: Session = Depends(get_db)):
    if not email:
        return {"history": []}
        
    all_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_email == email)
        .order_by(ChatMessage.id.asc())
        .all()
    )
    
    # Group messages by thread_id to build individual conversation links
    grouped_threads = {}
    for msg in all_messages:
        tid = msg.thread_id if msg.thread_id else f"legacy_{msg.id}"
        if tid not in grouped_threads:
            grouped_threads[tid] = {
                "id": msg.id,
                "thread_id": tid,
                "user_query": msg.user_query, # Uses first query as sidebar title
                "ai_response": msg.ai_response
            }
            
    return {"history": list(grouped_threads.values())}

@app.get("/api/thread")
def get_specific_thread(id: int, db: Session = Depends(get_db)):
    # Find the target message first to find its thread group string
    base_message = db.query(ChatMessage).filter(ChatMessage.id == id).first()
    
    if not base_message:
        return {"messages": [], "thread_id": None}
        
    # Handle matching criteria safely for rows that don't have a thread_id yet
    if base_message.thread_id:
        all_turns = (
            db.query(ChatMessage)
            .filter(ChatMessage.thread_id == base_message.thread_id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
        target_thread_id = base_message.thread_id
    else:
        # Fallback for old single-turn records left behind in the database
        all_turns = [base_message]
        target_thread_id = f"legacy_{base_message.id}"
    
    formatted_messages = []
    for turn in all_turns:
        formatted_messages.append({"text": turn.user_query, "sender": "user"})
        formatted_messages.append({"text": turn.ai_response, "sender": "bot"})
        
    return {"messages": formatted_messages, "thread_id": target_thread_id}

@app.post("/api/upload")
async def upload_user_document(
    email: str = Query(...), 
    file: UploadFile = File(...)
):
    """Receives personal documents and namespaces them safely within /uploads."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")
        
    allowed_extensions = {".pdf", ".txt", ".docx", ".doc"}
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed options: {', '.join(allowed_extensions)}"
        )
        
    user_folder_name = email.replace("@", "_").replace(".", "_")
    user_upload_directory = os.path.join(UPLOAD_DIR, user_folder_name)
    os.makedirs(user_upload_directory, exist_ok=True)
    
    safe_filename = "".join([c for c in file.filename if c.isalnum() or c in "._-"]).strip()
    file_path = os.path.join(user_upload_directory, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "message": "Document uploaded and tracked successfully",
            "filename": safe_filename,
            "saved_path": file_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store file layout structure: {str(e)}")

@app.get("/api/documents")
def list_user_documents(email: str = Query(...)):
    """Scans user folder and lists files."""
    user_folder_name = email.replace("@", "_").replace(".", "_")
    user_upload_directory = os.path.join(UPLOAD_DIR, user_folder_name)
    
    if not os.path.exists(user_upload_directory):
        return {"documents": []}
        
    try:
        all_files = [
            f for f in os.listdir(user_upload_directory) 
            if os.path.isfile(os.path.join(user_upload_directory, f))
        ]
        return {"documents": all_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query files repository: {str(e)}")

@app.post("/api/documents/process")
async def process_user_document(
    email: str = Query(..., description="The user's email address"),
    filename: str = Query(..., description="The exact filename of the uploaded document"),
    system_prompt: Optional[str] = Query(None, description="Custom processing instructions for the AI")
):
    # Reconstruct the user's specific uploads folder path
    safe_email_dir = email.replace("@", "_").replace(".", "_")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "uploads", safe_email_dir, filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"The file '{filename}' could not be located."
        )

    try:
        # Extract the raw text from the file using your universal doc_parser
        print(f"Parsing raw text from file: {filename}...")
        raw_text = parse_document(file_path, quiet=True)
        cleaned_doc_text = clean_text(raw_text)

        if not cleaned_doc_text.strip():
            return {
                "filename": filename,
                "status": "Skipped",
                "slm_analysis": "The target document appeared to be empty or unreadable."
            }

        # Handle default fallback for system instructions
        default_prompt = "Extract all core data and summarize the document contents."
        active_prompt = system_prompt if system_prompt else default_prompt

        # Initialize the local backend builder
        local_backend = build_backend(
            backend_name=None,   
            host=None,           
            model=None, # auto-detect model
            temperature=0.1,     
            max_tokens=2048,     
            timeout=120,         
            quiet=False          
        )

        print(f"Running local extraction pipeline for {filename}...")
        
        # Execute processing via local LLM engine
        ai_analysis = extract(
            text=cleaned_doc_text,
            system_prompt=active_prompt,
            backend=local_backend,
            fmt="text",
            chunk_size=4000,
            overlap=300,
            quiet=False
        )

        return {
            "filename": filename,
            "status": "Success",
            "slm_analysis": ai_analysis
        }

    except Exception as e:
        print(f"Pipeline execution crash error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during processing: {str(e)}"
        )

@app.delete("/api/documents")
def delete_user_document(email: str = Query(...), filename: str = Query(...)):
    user_folder_name = email.replace("@", "_").replace(".", "_")
    file_path = os.path.join(UPLOAD_DIR, user_folder_name, filename)
    
    if os.path.exists(file_path):
        os.remove(file_path) # Deletes file from disk storage layout
        return {"message": f"Successfully deleted {filename}"}
    else:
        raise HTTPException(status_code=404, detail="File not found on system disk.")

@app.post("/api/tracker/update")
def update_application_status(payload: TrackerStatusUpdate, db: Session = Depends(get_db)):
    """
    Handles application tracker updates. If 'rejected' is passed, it triggers
    the local SLM and scraping engine to find alternative community programs.
    """
    if payload.status.lower() == "rejected":
        return {
            "status": "Success",
            "message": "Status updated to Rejected.",
            "trigger_followup": True
        }
        
    return {"status": "Success", "message": f"Status updated to {payload.status}"}

class FPLRequest(BaseModel):
    income: float
    household_size: int
    state: Optional[str] = ""

@app.post("/api/fpl/calculate")
def calculate_fpl(req: FPLRequest):
    snapshot = calculate_fpl_snapshot(
        {"annual_income": req.income, "household_size": req.household_size}, 
        state=req.state
    )
    return snapshot

@app.get("/api/documents/deadlines")
def get_document_deadlines(email: str = Query(...), filename: str = Query(...)):
    user_folder_name = email.replace("@", "_").replace(".", "_")
    file_path = os.path.join(UPLOAD_DIR, user_folder_name, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    
    # We must import parse_document here or it's already imported
    # It is imported at the top: from parse_process.doc_parser import parse_document, clean_text
    raw_text = parse_document(file_path, quiet=True)
    report = build_deadline_report(clean_text(raw_text))
    return report

@app.post("/api/caseworker/notes")
def generate_caseworker_notes(report: dict):
    return {"notes": build_case_note(report)}