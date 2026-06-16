from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import database
from database import get_db, User, ChatMessage
from rag import generate_rag_response

app = FastAPI(title="CalHelpr Backend Engine")
database.init_db()

# Local file frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows browser local files to reach the ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request Data Validations ---
class UserAuth(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4)

class ChatInput(BaseModel):
    text: str
    user_id: int = None  # Tracks individual sessions if provided

# --- Endpoints ---
@app.post("/api/signup", status_code=status.HTTP_201_CREATED)
def signup(user_data: UserAuth, db: Session = Depends(get_db)):
    # Check if registration identity is already claimed
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username is already taken.")
    
    new_user = User(username=user_data.username, password=user_data.password)
    db.add(new_user)
    db.commit()
    return {"message": "Account registered successfully!", "user_id": new_user.id}

@app.post("/api/login")
def login(user_data: UserAuth, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_data.username).first()
    if not user or user.password != user_data.password:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    
    return {"message": "Access granted", "user_id": user.id, "username": user.username}

@app.post("/api/chat")
def process_chat(payload: ChatInput, db: Session = Depends(get_db)):
    user_raw_text = payload.text
    
    # Fetch AI RAG output context
    ai_raw_output = generate_rag_response(user_raw_text)
    
    # Add responsible AI safety guardrails in the message
    compliance_wrapper = (
        f"{ai_raw_output}\n\n"
        "ℹ️ *Guideline Notice: You may qualify for these community resources based on public files. "
        "Please confirm direct options with your caseworker before processing.*"
    )
    
    # Store record into local history
    db_chat = ChatMessage(
        user_id=payload.user_id, 
        user_query=user_raw_text, 
        ai_response=compliance_wrapper
    )
    db.add(db_chat)
    db.commit()
    
    return {"response": compliance_wrapper}

@app.get("/api/history")
def get_history(user_id: int = None, db: Session = Depends(get_db)):
    # Fetch user specific logs if logged in, otherwise fetch all recent anonymous entries
    if user_id:
        records = db.query(ChatMessage).filter(ChatMessage.user_id == user_id).all()
    else:
        records = db.query(ChatMessage).all()
        
    return {"history": records}