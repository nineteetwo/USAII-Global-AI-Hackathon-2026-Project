/* =============================================
   History Page Scripts
============================================= */
document.addEventListener('DOMContentLoaded', function () {
    var searchInput = document.getElementById('history-search-input');
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
