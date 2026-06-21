const BACKEND_URL = "http://127.0.0.1:8000";

// Dynamically check localStorage for the logged-in user's email
const currentUserEmail = localStorage.getItem("user_email") || "guest";

document.addEventListener("DOMContentLoaded", fetchUploadedDocuments);

// Handle file upload selection and submission
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fileInput = document.getElementById('fileInput').files[0];
    const statusDiv = document.getElementById('uploadStatus');

    if (!fileInput) return;

    statusDiv.style.color = "var(--text-secondary)";
    statusDiv.innerText = "Uploading to workspace repository...";

    const formData = new FormData();
    formData.append("file", fileInput);

    try {
        // Matches @app.post("/api/upload") passing email as a Query string parameter
        const response = await fetch(`${BACKEND_URL}/api/upload?email=${encodeURIComponent(currentUserEmail)}`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            statusDiv.style.color = "#27ae60";
            statusDiv.innerText = "File uploaded successfully!";
            document.getElementById('uploadForm').reset();
            
            // Instantly refresh the repository tracking view container
            fetchUploadedDocuments();
        } else {
            const err = await response.json();
            statusDiv.style.color = "#e53935";
            statusDiv.innerText = `Upload failed: ${err.detail || 'Server error'}`;
        }
    } catch (error) {
        statusDiv.style.color = "#e53935";
        statusDiv.innerText = `Network error: ${error.message}`;
    }
});

// Fetch files inside the user's isolated repository folder namespace
async function fetchUploadedDocuments() {
    const container = document.getElementById('fileListContainer');
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/documents?email=${encodeURIComponent(currentUserEmail)}`);
        
        if (!response.ok) {
            container.innerHTML = `<p class="empty-text" style="color: var(--emergency-bg);">Could not load your workspace file manager storage.</p>`;
            return;
        }

        const data = await response.json();
        const files = data.documents; // Matches your backend json signature: {"documents": [...]}

        if (!files || files.length === 0) {
            container.innerHTML = `<p class="empty-text">No workspace documents found. Upload a file above to add references for your RAG chatbot assistant.</p>`;
            return;
        }

        container.innerHTML = "";
        files.forEach(filename => {
            const fileRow = document.createElement('div');
            fileRow.className = 'file-item';
            fileRow.style.display = 'flex';
            fileRow.style.justifyContent = 'space-between';
            fileRow.style.alignItems = 'center';
            
            fileRow.innerHTML = `
                <div>
                    <i class="fa-regular fa-file-lines"></i>
                    <span class="file-name">${filename}</span>
                </div>
                <button class="delete-btn" onclick="deleteDocument('${filename}')" style="background:none; border:none; color:var(--emergency-bg, #e53935); cursor:pointer;">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            `;
            container.appendChild(fileRow);
        });

    } catch (error) {
        container.innerHTML = `<p class="empty-text" style="color: var(--emergency-bg);">Communication error: ${error.message}</p>`;
    }
}

async function deleteDocument(filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;

    try {
        const response = await fetch(`${BACKEND_URL}/api/documents?email=${encodeURIComponent(currentUserEmail)}&filename=${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            fetchUploadedDocuments(); // Automatically refresh the UI repository container look
        } else {
            alert("Failed to delete the document.");
        }
    } catch (error) {
        console.error("Error during deletion execution pipeline:", error);
    }
}