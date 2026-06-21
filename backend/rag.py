import os
import sys
import json
import builtins

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from parse_process.process_parse import build_backend
from parse_process.assistance_finder import find_assistance, format_report_markdown

def generate_rag_response(current_query: str, full_history: str = "", user_doc_path: str = "") -> str:
    """
    Executes the assistance finder pipeline using the uploaded document data 
    and chat history, returning the exact markdown report.
    """
    
    # Initialize local SLM backend engine 
    print("Initializing RAG backend engine...")
    backend = build_backend(
        backend_name="ollama",
        host=None,
        model="llama3.2:3b", 
        temperature=0.1,
        max_tokens=1024,
        timeout=300,
        quiet=True
    )
    
    # Extract context from the document if the user passed an active file path
    document_data = ""
    if user_doc_path:
        # Clean up the path string
        user_doc_path = user_doc_path.strip()
        
        # If it's just a raw filename or a relative path, resolve it explicitly
        if not os.path.isabs(user_doc_path):
            # Extract just the file name in case frontend passed an old 'uploads/' prefix
            base_filename = os.path.basename(user_doc_path)
            
            # Target the parse_process folder explicitly relative to CURRENT_DIR
            resolved_path = os.path.join(CURRENT_DIR, "parse_process", base_filename)
        else:
            resolved_path = user_doc_path

        print(f"RAG Pipeline: Searching for processed profile at: {resolved_path}")

        if os.path.exists(resolved_path):
            try:
                with open(resolved_path, "r", encoding="utf-8", errors="replace") as f:
                    file_content = f.read().strip()
                
                # Attempt to decode as JSON if it's already structured; otherwise, fall back to string
                try:
                    document_data = json.loads(file_content)
                    print("RAG Pipeline: Successfully loaded structured profile JSON data.")
                except json.JSONDecodeError:
                    document_data = file_content
                    print("RAG Pipeline: Successfully loaded profile plain-text data.")
                    
            except Exception as e:
                print(f"Error reading document context: {e}")
                document_data = ""
        else:
            print(f"PATH MISMATCH: File does not exist inside parse_process directory. Path tried: {resolved_path}")
            document_data = ""

    # Format conversations cleanly into strings, checking for None types safely
    # Ensure inputs are strings, default to empty string if None
    safe_history = str(full_history) if full_history is not None else ""
    safe_query = str(current_query) if current_query is not None else ""
    
    conversations_list = []
    if safe_history.strip():
        conversations_list.append(safe_history.strip())
        
    if safe_query.strip():
        conversations_list.append(f"User Question: {safe_query.strip()}")

    # If still empty, use a default string
    if not conversations_list:
        conversations_list = ["User requested eligibility options overview."]

    # Define static resource paths and handle missing databases gracefully
    database_path = os.path.join(CURRENT_DIR, "programs_db.json")
    if not os.path.exists(database_path):
        print(f"WARNING: Database file not found at {database_path}. Initializing placeholder array.")
        try:
            with open(database_path, "w", encoding="utf-8") as db_file:
                json.dump([], db_file)
        except Exception as write_err:
            return f"### Database Access Error\n\nFailed to initialize placeholder database: `{str(write_err)}`"

    try:
        print("Running assistance matching analysis...")

        # Output contents of report.md directly rather than regenerating report 
        # report_path = os.path.join(CURRENT_DIR, "parse_process", "report.md")
        # if os.path.exists(report_path):
        #     try:
        #         with open(report_path, "r", encoding="utf-8") as f:
        #             return f.read()
        #     except Exception as e:
        #         return f"Error reading report: {str(e)}"
            
        report = find_assistance(
            document_data=document_data,
            conversations=conversations_list,
            location="CA",  # Context seeds defaults to local region
            backend=backend,
            db_path=database_path,
            enable_web_fallback=True,
            quiet=True
        )
        
        # Generate markdown text response
        if not report:
            return "### Analysis Notice\n\nNo program definitions or fallback findings could be parsed for this request."
            
        exact_markdown_output = format_report_markdown(report)
        
        # Append a notice to the output if they are using an empty database file layout
        if os.path.exists(database_path) and os.path.getsize(database_path) <= 2:
            exact_markdown_output += (
                "\n\n---\n"
                "⚠️ **System Note for Development:** The database file `programs_db.json` is currently empty. "
                "Local database program matching was skipped, and results rely on the web fallback system."
            )

        return exact_markdown_output

    except Exception as e:
        print(f"RAG Pipeline error: {str(e)}")
        return (
            "### Service Notification\n\n"
            "I encountered an error analyzing your program eligibility options. "
            f"Details: `{str(e)}`"
        )