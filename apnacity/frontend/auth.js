// auth.js - login, signup, logout and page protection for ApnaCity
// Add to any page:  <script src="auth.js"></script>
//   - put  data-protected  on <body> to force login on that page
//   - give the login form id="loginForm" and the signup form id="signupForm"

const Auth = {

    // Who is logged in? Returns {email, role} or null
    async me() {
        try {
            const res = await fetch("/api/me", { credentials: "same-origin" });
            if (!res.ok) return null;
            return await res.json();
        } catch (err) {
            return null;
        }
    },

    // Send the visitor to the login page if they are not logged in
    async requireLogin() {
        const user = await Auth.me();
        if (!user) window.location.href = "login.html";
        return user;
    },

    async logout() {
        try {
            await fetch("/logout", { method: "POST", credentials: "same-origin" });
        } catch (err) {}
        window.location.href = "login.html";
    },

    // Login form: <form id="loginForm"> with inputs named email and password
    initLogin() {
        const form = document.getElementById("loginForm");
        if (!form) return;

        form.addEventListener("submit", async(e) => {
            e.preventDefault();
            Auth.showMessage(form, "");
            try {
                const res = await fetch("/login", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        email: form.email.value,
                        password: form.password.value
                    })
                });
                const data = await res.json();
                if (data.success) {
                    window.location.href = "Register_a_Issue.html";
                } else {
                    Auth.showMessage(form, data.message);
                }
            } catch (err) {
                Auth.showMessage(form, "Could not reach the server. Is civic.py running?");
            }
        });
    },

    // Signup form: <form id="signupForm"> (your signin.html)
    initSignup() {
        const form = document.getElementById("signupForm");
        if (!form) return;

        form.addEventListener("submit", async(e) => {
            e.preventDefault();

            const confirm = form["confirm-email"];
            if (confirm && form.email.value.trim().toLowerCase() !==
                confirm.value.trim().toLowerCase()) {
                alert("Email addresses do not match!");
                return;
            }

            const field = (name) => form[name] ? form[name].value : "";
            try {
                const res = await fetch("/signup", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        email: form.email.value,
                        password: form.password.value,
                        Fullname: field("Fullname"),
                        street: field("street"),
                        postalcode: field("postalcode"),
                        city: field("city"),
                        isAdmin: form.isAdmin ? form.isAdmin.checked : false
                    })
                });
                const data = await res.json();
                if (data.success) {
                    window.location.href = "Register_a_Issue.html";
                } else {
                    alert(data.message);
                }
            } catch (err) {
                alert("Could not reach the server. Is civic.py running?");
            }
        });
    },

    // Show an error under the form (creates <p class="auth-message"> if needed)
    showMessage(form, text) {
        let p = form.querySelector(".auth-message");
        if (!p) {
            p = document.createElement("p");
            p.className = "auth-message";
            p.style.cssText = "color:#c34242;text-align:center;margin-top:14px;font-size:14px;";
            form.appendChild(p);
        }
        p.textContent = text;
    },

    // Swap the "Login" link in the navbar for "Logout" when logged in
    async updateNav() {
        const nav = document.getElementById("navbar");
        if (!nav) return;
        const user = await Auth.me();
        if (!user) return;

        nav.querySelectorAll('a[href="login.html"], a[href="signin.html"]').forEach((a) => {
            if (a.getAttribute("href") === "signin.html") {
                a.parentElement.remove();
            } else {
                a.textContent = "Logout";
                a.href = "#";
                a.title = user.email;
                a.addEventListener("click", (e) => {
                    e.preventDefault();
                    Auth.logout();
                });
            }
        });
    }
};

document.addEventListener("DOMContentLoaded", () => {
    if (document.body.hasAttribute("data-protected")) Auth.requireLogin();
    Auth.initLogin();
    Auth.initSignup();
    Auth.updateNav();
});