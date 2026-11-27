// =====================================================
// APNACITY - COMPLETE REPORT SUBMISSION
// =====================================================

(function () {
    "use strict";

    const $ = (id) => document.getElementById(id);

    const getValue = (id) => {
        const element = $(id);
        return element && element.value
            ? element.value.trim()
            : "";
    };

    const ai = {
        category: "",
        severity: ""
    };

    let submitting = false;

    const form = $("reportForm");
    const submitBtn = $("submitBtn");
    const photoInput = $("photo");

    if (!form) {
        console.error("ApnaCity: reportForm not found.");
        return;
    }

    // -------------------------------------------------
    // API HELPERS
    // -------------------------------------------------

    async function apiRequest(url, options) {
        const response = await fetch(url, Object.assign({
            credentials: "same-origin"
        }, options || {}));

        const raw = await response.text();

        let data;

        try {
            data = raw ? JSON.parse(raw) : {};
        } catch (error) {
            data = {
                success: false,
                message: "Server returned an invalid response."
            };
        }

        if (response.status === 401) {
            window.location.href = "login.html";
            throw new Error("Please log in again.");
        }

        if (!response.ok) {
            let message = data.message || "Request failed.";

            if (response.status === 405) {
                message = "405 Method Not Allowed. Check the Flask route and request method.";
            } else if (response.status === 404) {
                message = "404 API route not found. Check the Flask URL.";
            } else if (response.status === 500) {
                message = data.message || "Server error. Check the Flask terminal.";
            }

            throw new Error(message);
        }

        return data;
    }

    function setStatus(element, message, isError) {
        if (!element) return;

        element.textContent = message;
        element.className = "status-text" + (
            isError ? " error" : ""
        );

        element.style.display = "block";
    }

    // -------------------------------------------------
    // LOCATION
    // -------------------------------------------------

    window.getLocation = function () {
        const status = $("locationStatus");

        if (!navigator.geolocation) {
            setStatus(status, "Location is not supported.", true);
            return;
        }

        setStatus(status, "Getting your location...", false);

        navigator.geolocation.getCurrentPosition(
            function (position) {
                if ($("latitude")) {
                    $("latitude").value =
                        position.coords.latitude.toFixed(6);
                }

                if ($("longitude")) {
                    $("longitude").value =
                        position.coords.longitude.toFixed(6);
                }

                setStatus(status, "Location captured successfully.", false);
            },
            function () {
                setStatus(
                    status,
                    "Location unavailable. Allow location permission.",
                    true
                );
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    };

    // -------------------------------------------------
    // CREATE AI COMPLAINT PANEL
    // -------------------------------------------------

    function createAIPanel() {
        if ($("genLetterBtn")) return;

        if (!submitBtn || !submitBtn.parentNode) {
            console.error("ApnaCity: Submit button not found.");
            return;
        }

        const panel = document.createElement("div");

        panel.id = "aiComplaintPanel";

        panel.style.cssText =
            "margin:15px 0;padding:16px;" +
            "border:1px solid #176b4a;" +
            "border-radius:10px;background:#f4f8f5;";

        panel.innerHTML = `
            <h3 style="margin:0 0 8px;">
                Complaint written by AI
            </h3>

            <p style="font-size:13px;color:#555;">
                Generate a formal complaint letter from your issue details.
            </p>

            <select id="letterLang"
                style="padding:10px;border:1px solid #ccc;border-radius:8px;">
                <option value="English">English</option>
                <option value="Hindi">हिन्दी (Hindi)</option>
            </select>

            <button type="button" id="genLetterBtn"
                class="location-btn"
                style="width:auto;padding:10px 16px;margin:10px 0;">
                Write complaint with AI
            </button>

            <p id="letterStatus" class="status-text"></p>

            <textarea id="letterText"
                placeholder="Your AI-generated complaint will appear here..."
                style="
                    display:none;
                    width:100%;
                    min-height:280px;
                    padding:12px;
                    border:1px solid #ccc;
                    border-radius:8px;
                    box-sizing:border-box;
                    font-size:14px;
                    line-height:1.6;
                "></textarea>

            <p id="letterHint"
                style="display:none;font-size:12px;color:#666;">
                Review and edit the letter before submitting.
            </p>
        `;

        submitBtn.parentNode.insertBefore(panel, submitBtn);
    }

    createAIPanel();

    // Optional phone number
    function addPhoneField() {
        if ($("phone") || !submitBtn) return;

        const wrapper = document.createElement("div");

        wrapper.className = "form-group";

        wrapper.innerHTML = `
            <label for="phone">Mobile number (optional)</label>
            <input id="phone" type="tel"
                maxlength="15"
                inputmode="numeric"
                placeholder="Mobile number">
        `;

        submitBtn.parentNode.insertBefore(
            wrapper,
            $("aiComplaintPanel") || submitBtn
        );
    }

    addPhoneField();

    // NGO permission checkbox
    function addNGOField() {
        if ($("shareNgo") || !submitBtn) return;

        const wrapper = document.createElement("div");

        wrapper.style.margin = "15px 0";

        wrapper.innerHTML = `
            <label style="display:flex;gap:8px;align-items:center;">
                <input type="checkbox" id="shareNgo" checked>
                <span>
                    Allow verified NGOs to view this complaint without
                    your name or contact details.
                </span>
            </label>
        `;

        submitBtn.parentNode.insertBefore(wrapper, submitBtn);
    }

    addNGOField();

    // -------------------------------------------------
    // PHOTO ANALYSIS
    // -------------------------------------------------

    if (photoInput) {
        photoInput.addEventListener("change", async function () {
            const file = photoInput.files[0];

            if (!file) return;

            let output = $("aiResult");

            if (!output) {
                output = document.createElement("p");
                output.id = "aiResult";
                output.className = "status-text";
                photoInput.parentNode.appendChild(output);
            }

            if (!file.type || file.type.indexOf("image/") !== 0) {
                setStatus(output, "Select a valid image.", true);
                return;
            }

            setStatus(output, "Analyzing your photo...", false);

            const formData = new FormData();
            formData.append("image", file);

            try {
                const data = await apiRequest("/api/analyze", {
                    method: "POST",
                    body: formData
                });

                if (!data.is_valid_issue) {
                    setStatus(
                        output,
                        "This image does not appear to show a civic issue.",
                        true
                    );
                    return;
                }

                ai.category = data.category || "";
                ai.severity = data.severity || "";

                if ($("Issue") && !$("Issue").value.trim()) {
                    $("Issue").value = data.description || "";
                }

                setStatus(
                    output,
                    (data.category || "Issue") +
                    " - " +
                    (data.severity || "Medium") +
                    ": " +
                    (data.description || "Photo analyzed."),
                    false
                );

            } catch (error) {
                console.error("Photo analysis:", error);
                setStatus(output, error.message, true);
            }
        });
    }

    // -------------------------------------------------
    // AI COMPLAINT LETTER
    // -------------------------------------------------

    async function generateLetter() {
        const issue = getValue("Issue");
        const button = $("genLetterBtn");
        const status = $("letterStatus");

        if (!issue || issue.length < 10) {
            setStatus(
                status,
                "Please describe the issue using at least 10 characters.",
                true
            );
            return false;
        }

        if (!button) {
            setStatus(status, "AI button not found.", true);
            return false;
        }

        button.disabled = true;

        setStatus(
            status,
            "AI is writing your formal complaint...",
            false
        );

        try {
            const data = await apiRequest("/api/generate-complaint", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    issue: issue,
                    city: getValue("city"),
                    area: getValue("Area"),
                    latitude: getValue("latitude"),
                    longitude: getValue("longitude"),
                    language: getValue("letterLang") || "English",
                    has_photo: !!(
                        photoInput &&
                        photoInput.files &&
                        photoInput.files.length
                    )
                })
            });

            if (!data.success || !data.letter) {
                throw new Error(
                    data.message || "AI returned an empty complaint."
                );
            }

            $("letterText").value = data.letter;
            $("letterText").style.display = "block";
            $("letterHint").style.display = "block";

            ai.category = data.category || ai.category;
            ai.severity = data.severity || ai.severity;

            setStatus(
                status,
                "Your AI complaint letter is ready. Review it before submitting.",
                false
            );

            return true;

        } catch (error) {
            console.error("AI letter error:", error);
            setStatus(status, error.message, true);
            return false;

        } finally {
            button.disabled = false;
        }
    }

    if ($("genLetterBtn")) {
        $("genLetterBtn").addEventListener("click", generateLetter);
    }

    // -------------------------------------------------
    // COMPLAINT SUCCESS DISPLAY
    // -------------------------------------------------

    function showSuccess(data, photoWarning) {
        const box = $("result");

        if (!box) {
            alert("Complaint submitted. ID: " + data.complaint_id);
            return;
        }

        box.replaceChildren();
        box.style.display = "block";

        const heading = document.createElement("h3");
        heading.textContent = "Report submitted successfully!";
        box.appendChild(heading);

        const analysis = data.analysis || {};

        const details = [
            "Complaint ID: " + (data.complaint_id || ""),
            "Category: " + (analysis.category || ai.category || "General"),
            "Responsible authority: " +
                (analysis.responsible_authority || "Municipal Corporation"),
            "Priority: " + (analysis.severity || ai.severity || "Medium")
        ];

        details.forEach(function (item) {
            const p = document.createElement("p");
            p.textContent = item;
            box.appendChild(p);
        });

        const link = document.createElement("a");
        link.href = "Track_report_status.html";
        link.textContent = "Track your complaint";

        box.appendChild(link);

        if (photoWarning) {
            const warning = document.createElement("p");
            warning.textContent = photoWarning;
            box.appendChild(warning);
        }

        box.scrollIntoView({
            behavior: "smooth"
        });
    }

    // -------------------------------------------------
    // SUBMIT REPORT
    // -------------------------------------------------

    form.addEventListener("submit", async function (event) {
        event.preventDefault();

        if (submitting) return;

        const status = $("submitStatus");
        const button = submitBtn;
        const issue = getValue("Issue");

        if (!issue) {
            setStatus(status, "Please enter your issue description.", true);
            return;
        }

        if (issue.length < 5) {
            setStatus(status, "Please provide more issue details.", true);
            return;
        }

        submitting = true;

        if (button) button.disabled = true;

        setStatus(status, "Preparing your complaint...", false);

        try {
            // Try to generate an AI letter if one is not already present.
            if (
                $("letterText") &&
                !$("letterText").value.trim() &&
                issue.length >= 10
            ) {
                const generated = await generateLetter();

                if (!generated) {
                    setStatus(
                        status,
                        "AI letter generation failed. You can try again or submit without the letter.",
                        true
                    );

                    const proceed = window.confirm(
                        "The AI complaint letter could not be generated. Submit the report without the AI letter?"
                    );

                    if (!proceed) return;
                }
            }

            setStatus(status, "Submitting your report...", false);

            const payload = {
                city: getValue("city"),
                Area: getValue("Area"),
                issue: issue,
                latitude: getValue("latitude"),
                longitude: getValue("longitude"),
                category: ai.category,
                severity: ai.severity,
                letter: getValue("letterText"),
                phone: getValue("phone"),
                share_with_ngos: !!(
                    $("shareNgo") && $("shareNgo").checked
                )
            };

            const data = await apiRequest("/api/reports", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            if (!data.success || !data.complaint_id) {
                throw new Error(
                    data.message || "The report was not saved."
                );
            }

            // Upload complaint photo after report creation.
            let photoWarning = "";

            if (
                photoInput &&
                photoInput.files &&
                photoInput.files.length > 0
            ) {
                const photoData = new FormData();

                photoData.append("image", photoInput.files[0]);
                photoData.append("kind", "before");

                try {
                    await apiRequest(
                        "/api/reports/" +
                        encodeURIComponent(data.complaint_id) +
                        "/photo",
                        {
                            method: "POST",
                            body: photoData
                        }
                    );
                } catch (error) {
                    photoWarning =
                        "Complaint saved, but photo upload failed: " +
                        error.message;
                }
            }

            setStatus(status, "", false);

            showSuccess(data, photoWarning);

        } catch (error) {
            console.error("Report submission error:", error);

            setStatus(status, error.message, true);

        } finally {
            submitting = false;

            if (button) button.disabled = false;
        }
    });

    console.log("ApnaCity report.js loaded successfully.");

})();
