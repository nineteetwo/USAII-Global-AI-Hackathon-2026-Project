import os
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base
from typing import Optional

import database
from database import get_db, User, ChatMessage
from rag import generate_rag_response

app = FastAPI(title="CalHelpr Backend Engine")

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
UPLOAD_DIR = "./uploads"
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
    uploaded_file_path: Optional[str] = ""  # Lets JS attach the path returned by /api/upload

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

@app.get("/api/chat")
def process_chat_get(text: str = "Hello"):
    """Temporary GET route to bypass the 405 Method Error."""
    from rag import generate_rag_response
    ai_raw_output = generate_rag_response(text)
    return {
        "response": f"{ai_raw_output}\nℹ️ *Notice: Connected via bypass channel.*"
    }

@app.post("/api/chat")
def process_chat(payload: ChatInput, db: Session = Depends(get_db)):
    # Most recent message string
    most_recent_message = payload.text
    target_rag_document_path = payload.uploaded_file_path or ""
    
    # Automatic path lookup
    if not target_rag_document_path and payload.email:
        user_folder_name = payload.email.replace("@", "_").replace(".", "_")
        user_upload_directory = os.path.join(UPLOAD_DIR, user_folder_name)
        
        if os.path.exists(user_upload_directory):
            all_files = [
                os.path.join(user_upload_directory, f) 
                for f in os.listdir(user_upload_directory) 
                if os.path.isfile(os.path.join(user_upload_directory, f))
            ]
            if all_files:
                all_files.sort(key=os.path.getmtime)
                target_rag_document_path = all_files[-1]

    # Compile the entire conversation history into one big text string
    conversation_history_string = ""
    if payload.email: 
        all_past_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_email == payload.email) 
            .order_by(ChatMessage.id.desc()) # Newest to oldest
            .all()
        )
        
        for msg in all_past_messages:
            conversation_history_string += f"User: {msg.user_query}\nBot: {msg.ai_response}\n"

    # Run the updated parameters into your generation library script
    ai_raw_output = generate_rag_response(
        current_query=most_recent_message,
        full_history=conversation_history_string,
        user_doc_path=target_rag_document_path
    )
    
    # Add safety guardrails
    compliance_wrapper = (
        f"{ai_raw_output}\n"
        "ℹ️ *Guideline Notice: You may qualify for these community resources based on public files. "
        "Please confirm direct options with your caseworker before processing.*"
    )
    
    # Store this new turn into local history database
    db_chat = ChatMessage(
        user_email=payload.email if payload.email else None,
        user_query=most_recent_message, 
        ai_response=compliance_wrapper
    )
    db.add(db_chat)
    db.commit()
    
    return {"response": compliance_wrapper, "id": db_chat.id}

@app.get("/api/history")
def get_history(email: str = None, db: Session = Depends(get_db)):
    """Retrieves previous chat conversations from the database."""
    if email: 
        records = db.query(ChatMessage).filter(ChatMessage.user_email == email).all()
    else:
        records = db.query(ChatMessage).filter(ChatMessage.user_email == None).all()
        
    return {"history": records}

@app.get("/api/thread")
def get_specific_thread(id: int, db: Session = Depends(get_db)):
    """Fetches a single conversation record matching the given ID to render it back on screen."""
    chat_record = db.query(ChatMessage).filter(ChatMessage.id == id).first()
    if not chat_record:
        raise HTTPException(status_code=404, detail="Chat conversation not found.")
    
    return {
        "messages": [
            {"text": chat_record.user_query, "sender": "user"},
            {"text": chat_record.ai_response, "sender": "bot"}
        ]
    }

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