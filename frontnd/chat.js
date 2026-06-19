/* =============================================
   Chat Page Scripts
============================================= */
document.addEventListener('DOMContentLoaded', function () {
    var chatInput = document.getElementById('chat-input');
    var chatMessagesContainer = document.querySelector('.chat-messages'); 
    var sidebarContainer = document.querySelector('.sidebar .chat-list');

    // Display User Session Info into Sidebar UI 
    var savedName = localStorage.getItem('calhelpr_name');
    var sidebarNameSpan = document.getElementById('sidebar-name');
    var sidebarSigninText = document.getElementById('sidebar-signin-text');
    var topBarSignInLink = document.getElementById('sign-in-link');

    if (savedName) {
        if (sidebarNameSpan) sidebarNameSpan.innerText = savedName;
        if (sidebarSigninText) sidebarSigninText.style.display = 'none';
        if (topBarSignInLink) {
            topBarSignInLink.innerText = "Sign Out";
            topBarSignInLink.href = "#";
            topBarSignInLink.addEventListener('click', function(e) {
                e.preventDefault();
                
                if (chatMessagesContainer) {
                    chatMessagesContainer.innerHTML = '';
                }
                
                localStorage.clear(); 
                window.location.reload();
            });
        }
    }

    // State variable to store our unique session thread identifier string
    var runtimeThreadSessionString = null;

    // Helper to get thread database row fallback ID from the live URL state
    function getActiveThreadRowId() {
        var urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('thread');
    }

    if (sidebarContainer) {
        fetchSidebarHistory();
    }

    var initialRowId = getActiveThreadRowId();
    if (initialRowId && chatMessagesContainer) {
        loadSpecificThread(initialRowId);
    }

    async function fetchSidebarHistory() {
        try {
            var activeUserEmail = localStorage.getItem('calhelpr_email');
            var url = 'http://127.0.0.1:8000/api/history';
            
            if (activeUserEmail) {
                url += '?email=' + encodeURIComponent(activeUserEmail);
            }

            var response = await fetch(url);
            if (!response.ok) return;

            var data = await response.json();
            var records = data.history.reverse(); 

            if (sidebarContainer) {
                sidebarContainer.innerHTML = ''; 
                var currentActiveRowId = getActiveThreadRowId();

                records.forEach(function (record) {
                    var sidebarItem = document.createElement('a');
                    
                    sidebarItem.href = 'index.html?thread=' + encodeURIComponent(record.id);
                    sidebarItem.className = 'chat-item';
                    
                    if (currentActiveRowId && String(record.id) === String(currentActiveRowId)) {
                        sidebarItem.classList.add('active');
                        // Synchronize our session key track back onto runtime
                        runtimeThreadSessionString = record.thread_id;
                    }
                    
                    var sidebarTitle = record.user_query.length > 25 ? record.user_query.substring(0, 25) + "..." : record.user_query;
                    
                    sidebarItem.innerHTML = `
                        <i class="fa-regular fa-message"></i>
                        <span>${sidebarTitle}</span>
                    `;
                    sidebarContainer.appendChild(sidebarItem);
                });
            }
        } catch (error) {
            console.error("Failed to load sidebar logs:", error);
        }
    }

    async function loadSpecificThread(rowId) {
        try {
            var response = await fetch('http://127.0.0.1:8000/api/thread?id=' + encodeURIComponent(rowId));
            
            // Handle if the HTTP request outright reports a 404
            if (response.status === 404) {
                clearStaleThreadState(rowId);
                return;
            }

            if (!response.ok) return;

            var data = await response.json();
            
            // If the backend returns an empty room gracefully with no thread_id, clear the stale URL param
            if (data.thread_id === null && (!data.messages || data.messages.length === 0)) {
                clearStaleThreadState(rowId);
                return;
            }

            runtimeThreadSessionString = data.thread_id; // Sync tracking string

            if (chatMessagesContainer && data.messages) {
                chatMessagesContainer.innerHTML = ''; // Clear greeting
                data.messages.forEach(function (msg) {
                    appendMessageBubble(msg.text, msg.sender);
                });
            }
        } catch (error) {
            console.error("Failed to recover conversation thread data:", error);
        }
    }

    // Helper to clear bad/empty query parameters from the address bar
    function clearStaleThreadState(rowId) {
        console.warn(`Thread ID ${rowId} not found or empty in database. Resetting to empty session.`);
        var cleanUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
        window.history.replaceState({}, '', cleanUrl);
        runtimeThreadSessionString = null;
    }

    // Interactive continuous multi-turn event listener loop
    if (chatInput && chatMessagesContainer) {
        chatInput.addEventListener('keydown', async function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();

                var userText = chatInput.value.trim();
                if (userText === '') return false;

                chatInput.value = '';

                // Append user bubble instantly
                appendMessageBubble(userText, 'user');
                
                // Append thinking placeholder bubble
                var loadingBubble = appendMessageBubble('Thinking...', 'bot');
                var textContainer = loadingBubble.querySelector('.message-text');

                try {
                    var activeUserEmail = localStorage.getItem('calhelpr_email');

                    var response = await fetch('http://127.0.0.1:8000/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            text: userText,
                            email: activeUserEmail ? activeUserEmail : null,
                            thread_id: runtimeThreadSessionString // Pass current thread group key
                        }),
                    });

                    var data = await response.json();

                    if (response.ok) {
                        // Swap out 'Thinking...' text container natively without refreshes
                        textContainer.innerText = data.response;
                        
                        // Set unique room identifier context
                        runtimeThreadSessionString = data.thread_id;
                        
                        var currentActiveRowId = getActiveThreadRowId();
                        // Lock current view window onto this thread's URL parameters context route
                        if (!currentActiveRowId && data.id) {
                            var newUrl = window.location.protocol + "//" + window.location.host + window.location.pathname + '?thread=' + encodeURIComponent(data.id);
                            window.history.pushState({ path: newUrl }, '', newUrl);
                            
                            // Force-load the new database logs so it loads right away
                            loadSpecificThread(data.id);
                        }
                        
                        // Re-render sidebar navigation items gently
                        fetchSidebarHistory();
                    } else {
                        textContainer.innerText = "Error: " + (data.detail || "Something went wrong.");
                    }

                } catch (error) {
                    console.error("Backend connection error:", error);
                    textContainer.innerText = "Unable to connect to CalHelpr service. Please check your local connection.";
                }
                return false;
            }
        });
    }

    function appendMessageBubble(text, sender) {
        var msgDiv = document.createElement('div');
        msgDiv.className = 'message ' + sender; 

        var avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = sender === 'user' ? '<i class="fa-regular fa-user"></i>' : '<i class="bi bi-plus-lg"></i>';

        var contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        var textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.innerText = text;

        contentDiv.appendChild(textDiv);
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(contentDiv);
        
        chatMessagesContainer.appendChild(msgDiv);
        chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;

        return msgDiv;
    }
    
});