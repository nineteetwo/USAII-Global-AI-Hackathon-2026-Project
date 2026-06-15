/* =============================================
   Chat Page Scripts
============================================= */
document.addEventListener('DOMContentLoaded', function () {
    var chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && chatInput.value.trim() !== '') {
                e.preventDefault();
                chatInput.value = '';
            }
        });
    }
});
