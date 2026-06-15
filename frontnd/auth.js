/* =============================================
   Auth Scripts (Login & Signup)
============================================= */
document.addEventListener('DOMContentLoaded', function () {
    /* ========== Utility: password toggle ========== */
    function setupPasswordToggle(toggleId, fieldId) {
        var btn = document.getElementById(toggleId);
        var field = document.getElementById(fieldId);
        if (!btn || !field) return;

        btn.addEventListener('click', function () {
            var icon = btn.querySelector('i');
            if (field.type === 'password') {
                field.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                field.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    }

    /* Login page toggle */
    setupPasswordToggle('toggle-password', 'login-password');

    /* Signup page toggle */
    setupPasswordToggle('toggle-signup-password', 'signup-password');

    /* ========== Login form submit ========== */
    var loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', function (e) {
            e.preventDefault();
            window.location.href = 'index.html';
        });
    }

    /* ========== Signup form submit ========== */
    var signupForm = document.getElementById('signup-form');
    if (signupForm) {
        signupForm.addEventListener('submit', function (e) {
            e.preventDefault();
            var password = document.getElementById('signup-password');
            var confirm = document.getElementById('signup-confirm');

            if (password && confirm && password.value !== confirm.value) {
                confirm.setCustomValidity('Passwords do not match.');
                confirm.reportValidity();
                return;
            }
            window.location.href = 'login.html';
        });

        /* Clear custom validity when user types */
        var confirmField = document.getElementById('signup-confirm');
        if (confirmField) {
            confirmField.addEventListener('input', function () {
                confirmField.setCustomValidity('');
            });
        }
    }
});
