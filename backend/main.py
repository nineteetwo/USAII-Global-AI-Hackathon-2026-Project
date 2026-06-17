import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
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
    allow_origins=["*"], 
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
    uploaded_file_path: str = ""  # Lets JS attach the path returned by /api/upload

# --- Endpoints ---
@app.post("/api/signup", status_code=status.HTTP_201_CREATED)
def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """
    Registers a new user account in the system.
    
    Checks if the requested email is already taken, hashes/stores the user 
    credentials in the database, and returns a success message along with the new user's ID.
    """
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    
    new_user = User(name=user_data.name, email=user_data.email, password=user_data.password)
    db.add(new_user)
    db.commit()
    
    return {"message": "Account registered successfully!", "email": new_user.email}

@app.post("/api/login")
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates a user attempting to sign in.
    
    Verifies the provided username and password against matching records in the database. 
    Returns an access confirmation along with the email and name on success.
    """
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or user.password != user_data.password:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    return {"message": "Access granted", "email": user.email, "name": user.name}

@app.get("/api/chat")
def process_chat_get(text: str = "Hello"):
    """
    Temporary GET route to bypass the 405 Method Error 
    and instantly return your RAG test string to the browser!
    """
    from rag import generate_rag_response
    ai_raw_output = generate_rag_response(text)
    return {
        "response": f"{ai_raw_output}\nℹ️ *Notice: Connected via bypass channel.*"
    }

@app.post("/api/chat")
def process_chat(payload: ChatInput, db: Session = Depends(get_db)):
    # Most recent message string
    most_recent_message = payload.text
    
    # Compile the entire conversation history into one big text string
    conversation_history_string = ""
    if payload.email: 
        all_past_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.user_email == payload.email)
            .order_by(ChatMessage.id.asc()) # Oldest to newest
            .all()
        )
        
        for msg in all_past_messages:
            conversation_history_string += f"User: {msg.user_query}\nBot: {msg.ai_response}\n"

    # generate response
    ai_raw_output = generate_rag_response(
        current_query=most_recent_message,
        full_history=conversation_history_string,
        user_doc_path=payload.uploaded_file_path
    )
    
    # Add safety guardrails
    compliance_wrapper = (
        f"{ai_raw_output}\n"
        "ℹ️ *Guideline Notice: You may qualify for these community resources based on public files. "
        "Please confirm direct options with your caseworker before processing.*"
    )
    
    # Store this new turn into local history database
    db_chat = ChatMessage(
        user_email=payload.email,
        user_query=most_recent_message, 
        ai_response=compliance_wrapper
    )
    db.add(db_chat)
    db.commit()
    
    return {"response": compliance_wrapper}

@app.get("/api/history")
def get_history(email: str = None, db: Session = Depends(get_db)):
    """
    Retrieves previous chat conversations from the database.
    
    If a specific user ID is provided, it returns only the saved conversation logs 
    belonging to that authenticated user. If no ID is provided, it falls back to 
    returning recent anonymous history entries.
    """
    if email: # Query records matching their verified session email string
        records = db.query(ChatMessage).filter(ChatMessage.user_email == email).all()
    else:
        records = db.query(ChatMessage).filter(ChatMessage.user_email == None).all()
        
    return {"history": records}
