// Common JavaScript functions and animations

// Animate elements on page load
document.addEventListener('DOMContentLoaded', function () {
    const animateElements = document.querySelectorAll('.animate-on-load');
    animateElements.forEach((el, index) => {
        setTimeout(() => {
            el.classList.add('animate__animated', 'animate__fadeInUp');
        }, 100 * index);
    });

    // Initialize Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize page-specific UI
    initPage();
});

// Logout handler
function handleLogout() {
    fetch('/logout', { method: 'POST' })
        .then(() => window.location.href = '/')
        .catch(err => {
            console.error("Logout failed:", err);
        });
}

// Toggle custom input field visibility
function toggleCustomInput(selectId, inputId) {
    const select = document.getElementById(selectId);
    const inputContainer = document.getElementById(inputId);

    if (select && inputContainer) {
        inputContainer.style.display = select.value === 'other' ? 'block' : 'none';
        if (select.value === 'other') {
            const inputField = inputContainer.querySelector('input');
            if (inputField) inputField.focus();
        }
    }
}

// Ripple effect for button click
function addRippleEffect(buttons) {
    buttons.forEach(button => {
        button.addEventListener('click', function (e) {
            const ripple = document.createElement('span');
            ripple.classList.add('ripple');

            const rect = button.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;

            ripple.style.width = ripple.style.height = `${size}px`;
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;

            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        });
    });
}

// Page-specific initializers
function initPage() {
    // Add ripple effect to all .btn elements
    const buttons = document.querySelectorAll('.btn');
    addRippleEffect(buttons);

    // Attach logout to any .logout-btn
    const logoutButtons = document.querySelectorAll('.logout-btn');
    logoutButtons.forEach(btn => {
        btn.addEventListener('click', handleLogout);
    });

    // Handle dynamic custom field toggling
    const customToggles = [
        { select: 'subjectSelect', input: 'subjectOtherOption' },
        { select: 'resourceTypeSelect', input: 'resourceTypeOtherOption' },
        { select: 'examTypeSelect', input: 'examTypeOtherOption' }
    ];

    customToggles.forEach(({ select, input }) => {
        const selectEl = document.getElementById(select);
        if (selectEl) {
            toggleCustomInput(select, input); // trigger once on page load
            selectEl.addEventListener('change', () => {
                toggleCustomInput(select, input);
            });
        }
    });
}
