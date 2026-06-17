/* =============================================
   History Page Scripts
============================================= */
document.addEventListener('DOMContentLoaded', function () {
    var searchInput = document.getElementById('history-search-input');
    var historyContainer = document.querySelector('.chat-list') || document.body;

    // Pull data from database when page opens
    fetchConversationHistory();

    async function fetchConversationHistory() {
        try {
            var activeUserId = localStorage.getItem('calhelpr_user_id');
            var url = 'http://127.0.0.1:8000/api/history';
            if (activeUserId) {
                url += '?user_id=' + activeUserId;
            }

            var response = await fetch(url);
            if (!response.ok) return;

            var data = await response.json();
            var records = data.history; 

            // Clear out hardcoded items in the list if the container is valid
            if (document.querySelector('.chat-list')) {
                document.querySelector('.chat-list').innerHTML = '';
            }

            // Loop through database entries and inject them into the HTML layout
            records.forEach(function (record) {
                var historyItem = document.createElement('a');
                historyItem.href = '#';
                historyItem.className = 'chat-item history-item';

                // Use the first few words of what the user asked as the chat title
                var shortTitle = record.user_query.length > 15 ? record.user_query.substring(0, 15) + "..." : record.user_query;

                historyItem.innerHTML = `
                    <i class="fa-regular fa-message"></i>
                    <div class="history-content">
                        <span class="history-item-title" style="font-weight: 600; display:block;">${shortTitle}</span>
                        <small class="history-item-preview" style="opacity: 0.6; font-size: 0.75rem;">${record.ai_response.substring(0, 45)}...</small>
                    </div>
                `;

                historyContainer.appendChild(historyItem);
            });

        } catch (error) {
            console.error("Failed to load historical data logs from database:", error);
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', function () {
            var query = searchInput.value.toLowerCase().trim();
            var items = document.querySelectorAll('.history-item');
            var groups = document.querySelectorAll('.history-date-group');

            items.forEach(function (item) {
                var title = item.querySelector('.history-item-title');
                var preview = item.querySelector('.history-item-preview');
                var text = (title ? title.textContent : '') + ' ' + (preview ? preview.textContent : '');
                if (text.toLowerCase().indexOf(query) !== -1) {
                    item.classList.remove('hidden');
                } else {
                    item.classList.add('hidden');
                }
            });

            groups.forEach(function (group) {
                var visible = group.querySelectorAll('.history-item:not(.hidden)');
                if (visible.length === 0) {
                    group.classList.add('hidden');
                } else {
                    group.classList.remove('hidden');
                }
            });
        });
    }
});
