// other.js - small shared helpers used by every page
// Add to any page:  <script src="other.js"></script>
// It runs by itself: mobile menu + footer year. Helpers live on window.ApnaUtils.

window.ApnaUtils = {

    // Make text safe before putting it into innerHTML
    esc(value) {
        const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
        return String(value == null ? "" : value).replace(/[&<>"']/g, (c) => map[c]);
    },

    // "2026-11-25T10:30:00" -> "25 Nov 2026"
    formatDate(value) {
        const d = new Date(value);
        if (isNaN(d)) return "-";
        return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
    },

    // Mobile menu button (needs #menuToggle and #navbar)
    setupMobileMenu() {
        const toggle = document.getElementById("menuToggle") || document.getElementById("menu-toggle");
        const navbar = document.getElementById("navbar");
        if (!toggle || !navbar) return;

        toggle.addEventListener("click", () => {
            navbar.classList.toggle("active");
            const isOpen = navbar.classList.contains("active");
            toggle.setAttribute("aria-expanded", isOpen);
            toggle.innerHTML = isOpen ?
                '<i class="fa-solid fa-xmark"></i>' :
                '<i class="fa-solid fa-bars"></i>';
        });
    },

    // Footer year (needs <span id="year">)
    setFooterYear() {
        const el = document.getElementById("year");
        if (el) el.textContent = new Date().getFullYear();
    }
};

document.addEventListener("DOMContentLoaded", () => {
    ApnaUtils.setupMobileMenu();
    ApnaUtils.setFooterYear();
});