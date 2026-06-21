const BACKEND_URL = "http://127.0.0.1:8000";
const currentUserEmail = localStorage.getItem("calhelpr_email") || "guest";

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
            const uploadData = await response.json();

            if (uploadData.saved_path) {
                localStorage.setItem('calhelpr_last_upload_path', uploadData.saved_path);
                localStorage.setItem('calhelpr_last_upload_name', uploadData.filename);
            }
            statusDiv.style.color = "#27ae60";
            statusDiv.innerText = `File uploaded: ${uploadData.filename}`;
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
        const files = data.documents;

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
                <div>
                    <button class="action-btn" onclick="extractDeadlines('${filename}')" style="background:var(--primary); border:none; color:white; padding: 4px 8px; border-radius: 4px; cursor:pointer; margin-right: 10px; font-size: 0.8rem;">
                        <i class="fa-regular fa-clock"></i> Deadlines
                    </button>
                    <button class="delete-btn" onclick="deleteDocument('${filename}')" style="background:none; border:none; color:var(--emergency-bg, #e53935); cursor:pointer;">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
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
            fetchUploadedDocuments(); 
        } else {
            alert("Failed to delete the document.");
        }
    } catch (error) {
        console.error("Error during deletion execution pipeline:", error);
    }
}

async function extractDeadlines(filename) {
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.style.color = "var(--text-secondary)";
    statusDiv.innerText = `Extracting deadlines from ${filename}...`;

    try {
        const response = await fetch(`${BACKEND_URL}/api/documents/deadlines?email=${encodeURIComponent(currentUserEmail)}&filename=${encodeURIComponent(filename)}`);
        if (response.ok) {
            const data = await response.json();
            if (data.deadlines && data.deadlines.length > 0) {
                let report = `Found ${data.deadlines.length} deadlines for ${filename}:\n\n`;
                data.deadlines.forEach(d => {
                    report += `- ${d.date} (${d.days_until} days away): ${d.context}\n`;
                });
                alert(report);
                statusDiv.innerText = "Deadlines extracted successfully.";
            } else {
                alert(`No deadlines found in ${filename}.`);
                statusDiv.innerText = "No deadlines found.";
            }
        } else {
            const err = await response.json();
            alert(`Failed to extract deadlines: ${err.detail || 'Server error'}`);
            statusDiv.innerText = "Failed to extract deadlines.";
        }
    } catch (error) {
        alert(`Network error: ${error.message}`);
    }
}

async function calculateFPL(event) {
    event.preventDefault();
    const income = document.getElementById('fplIncome').value;
    const householdSize = document.getElementById('fplHousehold').value;
    const state = document.getElementById('fplState').value;
    
    const resultDiv = document.getElementById('fplResult');
    resultDiv.innerText = "Calculating...";
    
    try {
        const response = await fetch(`${BACKEND_URL}/api/fpl/calculate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ income: parseFloat(income), household_size: parseInt(householdSize), state: state })
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.fpl_percent !== null) {
                resultDiv.innerHTML = `
                    <strong>Annual Income:</strong> $${data.annual_income}<br>
                    <strong>Household Size:</strong> ${data.household_size}<br>
                    <strong>100% FPL Amount:</strong> $${data.fpl_100_amount}<br>
                    <strong>Your FPL Percentage:</strong> ${data.fpl_percent}%
                `;
            } else {
                resultDiv.innerText = data.notes.join(" ");
            }
        } else {
            resultDiv.innerText = "Failed to calculate FPL.";
        }
    } catch (error) {
        resultDiv.innerText = `Network error: ${error.message}`;
    }
}