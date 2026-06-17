/* =============================================
   Chat Page Scripts
============================================= */
document.addEventListener('DOMContentLoaded', function () {
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
            topBarSignInLink.addEventListener('click', function() {
                localStorage.clear(); 
                window.location.reload();
            });
        }
    }

    var chatInput = document.getElementById('chat-input');
    var chatMessagesContainer = document.querySelector('.chat-messages'); 
    var sidebarContainer = document.querySelector('.sidebar .chat-list');

    // Extract a specific conversation thread identifier from the browser's address bar
    var urlParams = new URLSearchParams(window.location.search);
    var activeThreadId = urlParams.get('thread');

    // Fetch and display sidebar history safely when the chat page loads
    if (sidebarContainer) {
        fetchSidebarHistory();
    }

    // If the user clicked a specific past conversation link, pull and load its content arrays
    if (activeThreadId && chatMessagesContainer) {
        loadSpecificThread(activeThreadId);
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

                records.forEach(function (record) {
                    var sidebarItem = document.createElement('a');
                    
                    sidebarItem.href = 'index.html?thread=' + encodeURIComponent(record.id);
                    sidebarItem.className = 'chat-item';
                    
                    if (activeThreadId && String(record.id) === String(activeThreadId)) {
                        sidebarItem.classList.add('active');
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

    async function loadSpecificThread(threadId) {
        try {
            var response = await fetch('http://127.0.0.1:8000/api/thread?id=' + encodeURIComponent(threadId));
            if (!response.ok) return;

            var data = await response.json();
            
            if (chatMessagesContainer && data.messages) {
                chatMessagesContainer.innerHTML = '';
                
                data.messages.forEach(function (msg) {
                    appendMessageBubble(msg.text, msg.sender);
                });
            }
        } catch (error) {
            console.error("Failed to recover specified conversation thread data:", error);
        }
    }

    if (chatInput && chatMessagesContainer) {
        chatInput.addEventListener('keydown', async function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();

                var userText = chatInput.value.trim();
                if (userText === '') 
                    return false;

                chatInput.value = '';

                appendMessageBubble(userText, 'user');
                var loadingBubble = appendMessageBubble('Thinking...', 'bot');
                var textContainer = loadingBubble.querySelector('.message-text');

                try {
                    var activeUserEmail = localStorage.getItem('calhelpr_email');

                    var response = await fetch('http://127.0.0.1:8000/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            text: userText,
                            email: activeUserEmail ? activeUserEmail : null
                        }),
                    });

                    var data = await response.json();

                    if (response.ok) {
                        textContainer.innerText = data.response;
                        
                        // If new chat, lock address parameters onto its newly saved record row
                        if (!activeThreadId && data.id) {
                            var newUrl = window.location.protocol + "//" + window.location.host + window.location.pathname + '?thread=' + encodeURIComponent(data.id);
                            window.history.pushState({ path: newUrl }, '', newUrl);
                            activeThreadId = data.id;
                        }
                        
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