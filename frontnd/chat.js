/* =============================================
   Chat Page Scripts
============================================= */
document.addEventListener('DOMContentLoaded', function () {
    // Display User Session Info into Sidebar UI 
    var savedUsername = localStorage.getItem('calhelpr_username');
    var sidebarUsernameSpan = document.getElementById('sidebar-username');
    var sidebarSigninText = document.getElementById('sidebar-signin-text');
    var topBarSignInLink = document.getElementById('sign-in-link');

    if (savedUsername) {
        if (sidebarUsernameSpan) {
            sidebarUsernameSpan.innerText = savedUsername;
        }
        // Hide "Sign in to save conversations" prompt text
        if (sidebarSigninText) {
            sidebarSigninText.style.display = 'none';
        }
        // Swap the header "Sign In" button to say "Sign Out"
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

    if (chatInput && chatMessagesContainer) {
        chatInput.addEventListener('keydown', async function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();

                // Store input text
                var userText = chatInput.value.trim();
                if (userText === '') 
                    return;

                console.log("user entered" + userText);
                chatInput.value = '';

                // Display temporary "Thinking..." placeholder bubble on screen
                appendMessageBubble(userText, 'user');
                var loadingBubble = appendMessageBubble('Thinking...', 'bot');
                var textContainer = loadingBubble.querySelector('.message-text');

                try {
                    // Grab user_id from localStorage if logged in
                    var activeUserId = localStorage.getItem('calhelpr_user_id');

                    // Send message to backend
                    var response = await fetch('http://127.0.0.1:8000/api/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ 
                            text: userText,
                            user_id: activeUserId ? parseInt(activeUserId) : null
                        }),
                    });

                    var data = await response.json();

                    // Replace placeholder bubble with RAG response
                    if (response.ok) {
                        textContainer.innerText = data.response;
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

    // Dynamic element injector matching the project's CSS wrappers
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