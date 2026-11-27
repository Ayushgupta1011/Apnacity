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

    // Adds the top menu (with a working phone menu button) to pages that have none.
    // Skipped on the login / signup / report-form pages and on pages with their own menu.
    ensureMenu() {
        const page = location.pathname.split("/").pop().toLowerCase();
        const standalone = ["login.html", "signin.html", "register_a_issue.html"];
        if (standalone.includes(page)) return;
        if (document.querySelector("header, nav, #navbar")) return;

        const css = document.createElement("style");
        css.textContent = `
            .ac-header{position:sticky;top:0;z-index:2000;display:flex;align-items:center;justify-content:space-between;
                padding:12px 6%;background:#fff;box-shadow:0 4px 15px rgba(0,0,0,.08);font-family:Arial,sans-serif;}
            .ac-brand{display:flex;align-items:center;gap:10px;color:#088178;text-decoration:none;font-size:22px;font-weight:700;}
            .ac-brand img{width:42px;height:42px;object-fit:contain;}
            .ac-nav{display:flex;align-items:center;gap:24px;list-style:none;margin:0;padding:0;}
            .ac-nav a{color:#222;font-size:14px;text-decoration:none;transition:.2s;}
            .ac-nav a:hover,.ac-nav a.ac-active{color:#176b4a;font-weight:600;}
            .ac-toggle{display:none;border:0;background:none;font-size:26px;color:#176b4a;cursor:pointer;padding:4px 8px;}
            @media(max-width:860px){
                .ac-toggle{display:block;}
                .ac-nav{display:none;position:absolute;top:100%;left:0;right:0;background:#fff;flex-direction:column;
                    align-items:flex-start;gap:0;padding:8px 6% 16px;box-shadow:0 8px 15px rgba(0,0,0,.08);}
                .ac-nav.ac-open{display:flex;}
                .ac-nav li{width:100%;}
                .ac-nav a{display:block;padding:12px 0;font-size:16px;border-bottom:1px solid #eef3ef;}
            }`;
        document.head.appendChild(css);

        const links = [
            ["index.html", "Home"],
            ["Register_a_Issue.html", "Report Issue"],
            ["Track_report_status.html", "Track Status"],
            ["verified_impact.html", "Verified Impact"],
            ["Ngo.html", "Organizations"],
            ["comunity.html", "Community Action"]
        ];

        const header = document.createElement("header");
        header.className = "ac-header";
        header.innerHTML = `
            <a class="ac-brand" href="index.html"><img src="img/logo.jpeg" alt="ApnaCity"><span>ApnaCity</span></a>
            <ul class="ac-nav" id="acNav">
                ${links.map(([href, label]) =>
                    `<li><a href="${href}"${href.toLowerCase() === page ? ' class="ac-active"' : ""}>${label}</a></li>`).join("")}
                <li><a href="login.html" id="acAuth">Login</a></li>
            </ul>
            <button class="ac-toggle" id="acToggle" type="button" aria-label="Toggle menu" aria-expanded="false">&#9776;</button>`;
        document.body.insertBefore(header, document.body.firstChild);

        const nav = document.getElementById("acNav");
        const toggle = document.getElementById("acToggle");
        toggle.addEventListener("click", () => {
            const open = nav.classList.toggle("ac-open");
            toggle.setAttribute("aria-expanded", open);
            toggle.innerHTML = open ? "&#10005;" : "&#9776;";
        });

        // Show Logout instead of Login when signed in
        Auth.me().then((user) => {
            if (!user) return;
            const link = document.getElementById("acAuth");
            link.textContent = "Logout";
            link.href = "#";
            link.title = user.email;
            link.addEventListener("click", (e) => {
                e.preventDefault();
                Auth.logout();
            });
        });
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
    Auth.ensureMenu();
    if (document.body.hasAttribute("data-protected")) Auth.requireLogin();
    Auth.initLogin();
    Auth.initSignup();
    Auth.updateNav();
});
