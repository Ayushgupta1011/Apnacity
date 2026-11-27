const API = "/api/community";

const state = {
    activities: [],
    myActivities: [],
    user: null
};

const $ = (selector) => document.querySelector(selector);

function escapeHTML(value) {
    return String(value ? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[char]);
}

function showToast(message) {
    const toast = $("#toast");
    toast.textContent = message;
    toast.classList.add("show");

    setTimeout(() => toast.classList.remove("show"), 3000);
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        credentials: "same-origin",
        ...options
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.message || data.error || `Request failed (${response.status})`);
    }

    return data;
}

function openModal(id) {
    $("#" + id).classList.add("show");
}

function closeModal(id) {
    $("#" + id).classList.remove("show");
}

document.querySelectorAll("[data-close]").forEach(button => {
    button.addEventListener("click", () => closeModal(button.dataset.close));
});

document.querySelectorAll(".modal").forEach(modal => {
    modal.addEventListener("click", event => {
        if (event.target === modal) modal.classList.remove("show");
    });
});

$("#openCreateBtn").addEventListener("click", () => {
    if (!state.user) {
        showToast("Please log in to create an activity.");
        return;
    }

    openModal("createModal");
});

async function loadUser() {
    try {
        const data = await api("/api/me");
        state.user = data.user || data;

        $("#loginLink").textContent = "My Account";
        $("#loginLink").href = "/profile";

    } catch {
        state.user = null;
    }
}

async function loadActivities() {
    const grid = $("#activityGrid");
    grid.innerHTML = '<div class="empty-state">Loading activities...</div>';

    try {
        const data = await api(`${API}/activities`);

        state.activities = Array.isArray(data) ?
            data :
            data.activities || [];

        renderActivities();
        updateStats();

    } catch (error) {
        grid.innerHTML = `
            <div class="empty-state">
                Unable to load activities.<br>
                ${escapeHTML(error.message)}
            </div>`;
    }
}

function renderActivities() {
    const grid = $("#activityGrid");
    const search = $("#searchActivity").value.toLowerCase();
    const category = $("#categoryFilter").value;
    const status = $("#statusFilter").value;

    const filtered = state.activities.filter(activity => {
        const title = String(activity.title || "").toLowerCase();
        const description = String(activity.description || "").toLowerCase();

        return (
            (!search || title.includes(search) || description.includes(search)) &&
            (!category || activity.category === category) &&
            (!status || activity.status === status)
        );
    });

    if (!filtered.length) {
        grid.innerHTML = '<div class="empty-state">No activities found.</div>';
        return;
    }

    grid.innerHTML = filtered.map(activity => {
                const id = Number(activity.id);
                const joined = Boolean(activity.joined);
                const image = activity.cover_image || activity.image_url;

                return `
            <article class="activity-card">
                <div class="activity-cover">
                    ${image
                        ? `<img src="${escapeHTML(image)}" alt="Activity photo" loading="lazy">`
                        : "🤝"}
                </div>

                <div class="activity-body">
                    <span class="activity-category">
                        ${escapeHTML(activity.category || "Community")}
                    </span>

                    <h3>${escapeHTML(activity.title)}</h3>

                    <p class="activity-description">
                        ${escapeHTML(activity.description)}
                    </p>

                    <div class="activity-meta">
                        <span>📍 ${escapeHTML(activity.location || activity.city || "Location not specified")}</span>
                        <span>📅 ${escapeHTML(activity.activity_date || "Date not specified")}</span>
                        <span>🕒 ${escapeHTML(activity.start_time || "")}</span>
                        <span>📌 ${escapeHTML(activity.status || "pending")}</span>
                    </div>

                    <div class="activity-footer">
                        <span class="volunteer-count">
                            👥 ${Number(activity.volunteer_count || 0)} volunteers
                        </span>

                        <button
                            class="join-btn"
                            data-action="join"
                            data-id="${id}"
                            ${joined || activity.status !== "approved" ? "disabled" : ""}
                        >
                            ${joined ? "Joined ✓" :
                                activity.status === "approved" ? "Join Activity" : "Not Open"}
                        </button>
                    </div>

                    <button class="details-btn"
                        data-action="details"
                        data-id="${id}">
                        View Details →
                    </button>
                </div>
            </article>
        `;
    }).join("");
}

function updateStats() {
    const activities = state.activities;

    $("#totalActivities").textContent = activities.filter(
        a => a.status === "approved"
    ).length;

    $("#completedActivities").textContent = activities.filter(
        a => a.status === "completed"
    ).length;

    $("#totalVolunteers").textContent = activities.reduce(
        (total, activity) => total + Number(activity.volunteer_count || 0), 0
    );

    $("#totalImpact").textContent = activities.reduce(
        (total, activity) => total + Number(activity.people_helped || 0), 0
    );
}

// CREATE ACTIVITY
$("#createActivityForm").addEventListener("submit", async event => {
    event.preventDefault();

    if (!state.user) {
        showToast("Please log in first.");
        return;
    }

    const form = event.currentTarget;
    const submitButton = form.querySelector("button[type=submit]");
    const formData = Object.fromEntries(new FormData(form).entries());

    formData.max_volunteers = Number(formData.max_volunteers || 50);

    submitButton.disabled = true;
    submitButton.textContent = "Submitting...";

    try {
        const data = await api(`${API}/activities`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(formData)
        });

        showToast(data.message || "Activity submitted for approval.");
        form.reset();
        closeModal("createModal");
        await loadActivities();

    } catch (error) {
        showToast(error.message);
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Submit Activity";
    }
});

// JOIN ACTIVITY
async function joinActivity(id, button) {
    if (!state.user) {
        showToast("Please log in to join this activity.");
        return;
    }

    button.disabled = true;
    button.textContent = "Joining...";

    try {
        const data = await api(`${API}/activities/${id}/join`, {
            method: "POST"
        });

        showToast(data.message || "Successfully joined!");
        await Promise.all([loadActivities(), loadMyActivities()]);

    } catch (error) {
        showToast(error.message);
        button.disabled = false;
        button.textContent = "Join Activity";
    }
}

// ACTIVITY DETAILS
async function showDetails(id) {
    const activity = state.activities.find(a => Number(a.id) === id);

    if (!activity) return;

    const image = activity.cover_image || activity.image_url;

    $("#activityDetails").innerHTML = `
        <span class="activity-category">${escapeHTML(activity.category)}</span>
        <h2>${escapeHTML(activity.title)}</h2>

        ${image ? `<img class="detail-photo" src="${escapeHTML(image)}" alt="Activity photo">` : ""}

        <p>${escapeHTML(activity.description)}</p>

        <div class="activity-meta">
            <span>📍 ${escapeHTML(activity.location || activity.city)}</span>
            <span>📅 ${escapeHTML(activity.activity_date)}</span>
            <span>👥 ${Number(activity.volunteer_count || 0)} volunteers</span>
            <span>Status: ${escapeHTML(activity.status)}</span>
        </div>

        <div class="detail-actions">
            <button data-action="join" data-id="${id}"
                ${activity.joined || activity.status !== "approved" ? "disabled" : ""}>
                ${activity.joined ? "Already Joined" : "Join Activity"}
            </button>

            <button data-action="photos" data-id="${id}">
                Upload Photos
            </button>

            <button data-action="attendance" data-id="${id}">
                Manage Attendance
            </button>

            <button data-action="impact" data-id="${id}">
                View Impact
            </button>
        </div>

        <div id="activityExtra"></div>
    `;

    openModal("detailsModal");
}

// PHOTO UPLOAD
async function uploadPhotos(id, files) {
    if (!state.user) {
        showToast("Please log in first.");
        return;
    }

    if (!files.length) {
        showToast("Select at least one photo.");
        return;
    }

    const formData = new FormData();

    Array.from(files).forEach(file => formData.append("photos", file));

    try {
        const data = await api(`${API}/activities/${id}/photos`, {
            method: "POST",
            body: formData
        });

        showToast(data.message || "Photos uploaded successfully.");
    } catch (error) {
        showToast(error.message);
    }
}

// ATTENDANCE
async function loadAttendance(id) {
    const extra = $("#activityExtra");
    extra.innerHTML = "<p>Loading attendance...</p>";

    try {
        const data = await api(`${API}/activities/${id}/attendance`);
        const participants = data.participants || [];

        extra.innerHTML = `
            <h3>Volunteer Attendance</h3>
            ${participants.length ? participants.map(person => `
                <div class="simple-card">
                    <p>${escapeHTML(person.name || person.user_id)}</p>
                    <p>Attendance: ${escapeHTML(person.attendance_status || "Not marked")}</p>
                    <button data-action="mark-attendance"
                        data-activity="${id}"
                        data-user="${Number(person.user_id)}">
                        Mark Present
                    </button>
                </div>
            `).join("") : "<p>No volunteers found.</p>"}
        `;
    } catch (error) {
        extra.textContent = error.message;
    }
}

async function markAttendance(activityId, userId) {
    try {
        const data = await api(
            `${API}/activities/${activityId}/attendance/${userId}`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ attendance_status: "present" })
            }
        );

        showToast(data.message || "Attendance updated.");
        await loadAttendance(activityId);

    } catch (error) {
        showToast(error.message);
    }
}

// IMPACT REPORT
async function loadActivityImpact(id) {
    const extra = $("#activityExtra");
    extra.innerHTML = "<p>Loading impact report...</p>";

    try {
        const data = await api(`${API}/activities/${id}/impact`);

        extra.innerHTML = `
            <div class="impact-card">
                <h3>Activity Impact</h3>
                <p>People helped: ${Number(data.people_helped || 0)}</p>
                <p>Volunteers: ${Number(data.volunteer_count || 0)}</p>
                <p>Work completed: ${escapeHTML(data.work_completed || "Not reported")}</p>
                <p>Verified: ${data.verified ? "Yes" : "Pending verification"}</p>
            </div>
        `;
    } catch (error) {
        extra.textContent = error.message;
    }
}

// MY ACTIVITIES
async function loadMyActivities() {
    const container = $("#myActivities");

    if (!state.user) {
        container.innerHTML = '<div class="empty-state">Log in to see your activities.</div>';
        return;
    }

    try {
        const data = await api(`${API}/my-activities`);
        state.myActivities = data.activities || [];

        if (!state.myActivities.length) {
            container.innerHTML = '<div class="empty-state">You have not joined any activities yet.</div>';
            return;
        }

        container.innerHTML = state.myActivities.map(activity => `
            <div class="simple-card">
                <h3>${escapeHTML(activity.title)}</h3>
                <p>${escapeHTML(activity.activity_date || "")}</p>
                <p>Participation: ${escapeHTML(activity.participation_status || "Joined")}</p>
                <button class="details-btn"
                    data-action="certificate"
                    data-id="${Number(activity.id)}">
                    Get Certificate
                </button>
            </div>
        `).join("");

    } catch (error) {
        container.innerHTML = `<div class="empty-state">${escapeHTML(error.message)}</div>`;
    }
}

// CERTIFICATE
async function getCertificate(id) {
    try {
        const response = await fetch(
            `${API}/activities/${id}/certificate`,
            { credentials: "same-origin" }
        );

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.message || "Certificate is not available.");
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        const link = document.createElement("a");
        link.href = url;
        link.download = `ApnaCity-Certificate-${id}.pdf`;
        link.click();

        URL.revokeObjectURL(url);

    } catch (error) {
        showToast(error.message);
    }
}

// EVENT DELEGATION
document.addEventListener("click", async event => {
    const button = event.target.closest("[data-action]");
    if (!button) return;

    const action = button.dataset.action;
    const id = Number(button.dataset.id);

    if (action === "join") {
        await joinActivity(id, button);
    }

    if (action === "details") {
        showDetails(id);
    }

    if (action === "photos") {
        const extra = $("#activityExtra");

        extra.innerHTML = `
            <h3>Upload Activity Photos</h3>
            <input type="file" id="activityPhotos"
                accept="image/jpeg,image/png,image/webp"
                multiple>
            <button class="primary-btn" id="uploadPhotoBtn">
                Upload Photos
            </button>
        `;

        $("#uploadPhotoBtn").addEventListener("click", async () => {
            await uploadPhotos(id, $("#activityPhotos").files);
        });
    }

    if (action === "attendance") {
        await loadAttendance(id);
    }

    if (action === "mark-attendance") {
        await markAttendance(
            Number(button.dataset.activity),
            Number(button.dataset.user)
        );
    }

    if (action === "impact") {
        await loadActivityImpact(id);
    }

    if (action === "certificate") {
        await getCertificate(id);
    }
});

// SEARCH AND FILTERS
$("#searchActivity").addEventListener("input", renderActivities);
$("#categoryFilter").addEventListener("change", renderActivities);
$("#statusFilter").addEventListener("change", renderActivities);

// INITIALIZE
async function initializeCommunity() {
    await loadUser();
    await loadActivities();
    await loadMyActivities();
}

initializeCommunity();