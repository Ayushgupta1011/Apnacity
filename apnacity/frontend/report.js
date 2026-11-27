// report.js - ApnaCity complaint submission
(function() {
    "use strict";

    const $ = (id) => document.getElementById(id);

    const ai = {
        category: "",
        severity: ""
    };

    let force = false;

    const form = $("reportForm");
    const submitBtn = $("submitBtn");

    if (!form) {
        console.error("ApnaCity: #reportForm was not found.");
        return;
    }

    // ---------- Helpers ----------

    async function readJson(response) {
        try {
            return await response.json();
        } catch {
            return {
                success: false,
                message: `Server returned an invalid response (${response.status}).`
            };
        }
    }

    function setStatus(element, message, isError = false) {
        if (!element) return;

        element.textContent = message;
        element.className = "status-text" + (isError ? " error" : "");
        element.style.display = "block";
    }

    function showApiError(response, data) {
        if (response.status === 405) {
            return "405 Method Not Allowed: Flask does not allow POST on /api/reports. Check the civic.py route.";
        }

        if (response.status === 404) {
            return "404: /api/reports was not found. Check the Flask API URL.";
        }

        if (response.status === 401) {
            window.location.href = "login.html";
            return "Please log in.";
        }

        return data.message || `Request failed (${response.status}).`;
    }

    // ---------- 1. Current location ----------

    window.getLocation = function() {
        const status = $("locationStatus");

        if (!navigator.geolocation) {
            setStatus(status, "Your browser does not support location.", true);
            return;
        }

        setStatus(status, "Getting your location...");

        navigator.geolocation.getCurrentPosition(
            (position) => {
                if ($("latitude")) {
                    $("latitude").value =
                        position.coords.latitude.toFixed(6);
                }

                if ($("longitude")) {
                    $("longitude").value =
                        position.coords.longitude.toFixed(6);
                }

                setStatus(status, "Location captured successfully.");
            },
            () => {
                setStatus(
                    status,
                    "Location unavailable. Please allow location permission.",
                    true
                );
            }, {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    };

    // ---------- 2. Photo analysis using AI ----------

    const photoInput = $("photo");

    if (photoInput) {
        photoInput.addEventListener("change", async function(event) {
            const file = event.target.files[0];

            if (!file) return;

            let output = $("aiResult");

            if (!output) {
                output = document.createElement("p");
                output.id = "aiResult";
                output.className = "status-text";
                photoInput.parentNode.appendChild(output);
            }

            if (!file.type.startsWith("image/")) {
                setStatus(output, "Please select a valid image.", true);
                return;
            }

            setStatus(output, "Analyzing your photo...");

            const formData = new FormData();
            formData.append("image", file);

            try {
                const response = await fetch("/api/analyze", {
                    method: "POST",
                    credentials: "same-origin",
                    body: formData
                });

                const data = await readJson(response);

                if (!response.ok) {
                    throw new Error(showApiError(response, data));
                }

                if (!data.is_valid_issue) {
                    setStatus(
                        output,
                        "This photo does not appear to show a civic issue.",
                        true
                    );
                    return;
                }

                ai.category = data.category || "";
                ai.severity = data.severity || "";

                setStatus(
                    output,
                    `${data.category || "Issue"} (${data.severity || "Unspecified"}): ${data.description || "Photo analyzed."}`
                );

                if ($("Issue") && !$("Issue").value.trim()) {
                    $("Issue").value = data.description || "";
                }

                if ($("category") && data.category) {
                    $("category").value = data.category;
                }

            } catch (error) {
                console.error("Photo analysis error:", error);
                setStatus(output, error.message, true);
            }
        });
    }

    // ---------- 3. Create AI complaint-letter panel ----------

    const anchor = $("submitBtn");

    if (anchor && anchor.parentNode && !$("genLetterBtn")) {
        const panel = document.createElement("div");

        panel.style.cssText =
            "margin:6px 0 18px;padding:16px;border:1px dashed #176b4a;" +
            "border-radius:10px;background:#f4f8f5;";

        panel.innerHTML = `
            <label style="display:block;font-weight:600;margin-bottom:6px;">
                Complaint written by AI
            </label>

            <p style="font-size:13px;color:#666;">
                AI will turn your issue description into a formal complaint.
            </p>

            <div style="display:flex;gap:10px;flex-wrap:wrap;">
                <select id="letterLang"
                    style="padding:10px;border:1px solid #ddd;border-radius:8px;">
                    <option value="English">English</option>
                    <option value="Hindi">हिन्दी (Hindi)</option>
                </select>

                <button type="button" id="genLetterBtn"
                    class="location-btn"
                    style="width:auto;margin:0;padding:10px 16px;">
                    Write complaint with AI
                </button>
            </div>

            <p id="letterStatus" class="status-text"></p>

            <textarea id="letterText"
                style="display:none;width:100%;min-height:300px;padding:12px;
                border:1px solid #ddd;border-radius:8px;font-size:14px;
                line-height:1.6;"></textarea>

            <p id="letterHint"
                style="display:none;font-size:12px;color:#888;">
                Review and edit the AI-generated complaint before submitting.
            </p>
        `;

        anchor.parentNode.insertBefore(panel, anchor);

        // Optional phone number field
        if (!$("phone")) {
            const phoneGroup = document.createElement("div");
            phoneGroup.className = "form-group";

            phoneGroup.innerHTML = `
                <label for="phone">Mobile number (optional)</label>
                <input type="tel" id="phone"
                    placeholder="10-digit mobile number"
                    inputmode="numeric" maxlength="15"
                    autocomplete="tel">
                <p style="font-size:12px;color:#888;">
                    SMS updates may be sent if SMS is enabled.
                </p>
            `;

            anchor.parentNode.insertBefore(phoneGroup, panel);
        }

        // NGO sharing permission
        if (!$("shareNgo")) {
            const shareBox = document.createElement("div");

            shareBox.style.cssText =
                "margin:0 0 18px;font-size:13px;color:#555;";

            shareBox.innerHTML = `
                <label style="display:flex;gap:8px;align-items:flex-start;">
                    <input type="checkbox" id="shareNgo" checked>
                    <span>
                        Allow verified NGOs to view this complaint without
                        your name or contact details.
                    </span>
                </label>
            `;

            anchor.parentNode.insertBefore(shareBox, panel);
        }
    }

    // ---------- 4. Generate AI complaint letter ----------

    async function generateLetter() {
        const issue = $("Issue") ? .value.trim() || "";
        const status = $("letterStatus");
        const button = $("genLetterBtn");

        if (issue.length < 10) {
            setStatus(
                status,
                "Please describe the issue in at least one sentence.",
                true
            );
            return false;
        }

        if (!button) return false;

        button.disabled = true;
        setStatus(status, "AI is writing your complaint...");

        try {
            const response = await fetch("/api/generate-complaint", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    issue: issue,
                    city: $("city") ? .value || "",
                    area: $("Area") ? .value || "",
                    latitude: $("latitude") ? .value || "",
                    longitude: $("longitude") ? .value || "",
                    language: $("letterLang") ? .value || "English",
                    has_photo: !!photoInput ? .files ? .length
                })
            });

            const data = await readJson(response);

            if (response.status === 401) {
                window.location.href = "login.html";
                return false;
            }

            if (!response.ok || !data.success || !data.letter) {
                throw new Error(showApiError(response, data));
            }

            $("letterText").value = data.letter;
            $("letterText").style.display = "block";
            $("letterHint").style.display = "block";

            ai.category = data.category || ai.category;
            ai.severity = data.severity || ai.severity;

            setStatus(
                status,
                data.ai_used === false ?
                "A standard complaint draft was prepared. Review it before submitting." :
                "Complaint ready. Review it before submitting."
            );

            return true;

        } catch (error) {
            console.error("AI complaint error:", error);
            setStatus(status, error.message, true);
            return false;

        } finally {
            button.disabled = false;
        }
    }

    $("genLetterBtn") ? .addEventListener("click", generateLetter);

    // ---------- 5. Duplicate complaint display ----------

    function showDuplicate(data, status) {
        const box = $("result");

        if (!box) return;

        box.replaceChildren();
        box.style.display = "block";

        const message = document.createElement("p");
        message.textContent =
            "A similar complaint was already reported nearby. " +
            "You can support the existing complaint or submit yours anyway.";

        box.appendChild(message);

        const supportButton = document.createElement("button");
        supportButton.type = "button";
        supportButton.textContent = "Support existing complaint";
        supportButton.className = "location-btn";

        supportButton.addEventListener("click", async() => {
            try {
                const response = await fetch(
                    "/api/reports/" +
                    encodeURIComponent(data.existing_id) +
                    "/support", {
                        method: "POST",
                        credentials: "same-origin"
                    }
                );

                const result = await readJson(response);

                if (!response.ok) {
                    throw new Error(showApiError(response, result));
                }

                box.textContent = result.message ||
                    "You supported the existing complaint.";

            } catch (error) {
                box.textContent = error.message;
            }
        });

        const anywayButton = document.createElement("button");
        anywayButton.type = "button";
        anywayButton.textContent = "Submit my complaint anyway";
        anywayButton.className = "location-btn";

        anywayButton.addEventListener("click", () => {
            force = true;
            form.requestSubmit();
        });

        box.append(supportButton, anywayButton);
        status.textContent = "";
    }

    // ---------- 6. Submit complaint ----------

    if (!form.dataset.reportHandlerAttached) {
        form.dataset.reportHandlerAttached = "true";

        form.addEventListener("submit", async function(event) {
            event.preventDefault();

            const status = $("submitStatus") || document.createElement("p");
            const button = $("submitBtn") || event.submitter;

            if (!status.parentNode) {
                form.appendChild(status);
            }

            const issue = $("Issue") ? .value.trim() || "";

            if (!issue) {
                setStatus(status, "Please describe your issue.", true);
                return;
            }

            // Generate the AI letter when the user has not generated one.
            if (
                $("letterText") &&
                !$("letterText").value.trim() &&
                issue.length >= 10
            ) {
                await generateLetter();
            }

            if (button) button.disabled = true;

            setStatus(status, "Submitting your complaint...");

            try {
                const payload = {
                    city: $("city") ? .value || "",
                    Area: $("Area") ? .value || "",
                    issue: issue,
                    latitude: $("latitude") ? .value || "",
                    longitude: $("longitude") ? .value || "",
                    category: ai.category,
                    severity: ai.severity,
                    letter: $("letterText") ? .value || "",
                    phone: $("phone") ? .value || "",
                    force: force,
                    share_with_ngos: $("shareNgo") ? .checked ? ? false
                };

                const response = await fetch("/api/reports", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify(payload)
                });

                const data = await readJson(response);

                if (response.status === 401) {
                    window.location.href = "login.html";
                    return;
                }

                if (response.status === 409 && data.duplicate) {
                    showDuplicate(data, status);
                    return;
                }

                if (!response.ok || !data.success) {
                    throw new Error(showApiError(response, data));
                }

                // Upload the photo after the complaint is saved.
                let photoWarning = "";

                const photoFile = photoInput ? .files ? .[0];

                if (photoFile && data.complaint_id) {
                    const photoData = new FormData();
                    photoData.append("image", photoFile);
                    photoData.append("kind", "before");

                    try {
                        const photoResponse = await fetch(
                            "/api/reports/" +
                            encodeURIComponent(data.complaint_id) +
                            "/photo", {
                                method: "POST",
                                credentials: "same-origin",
                                body: photoData
                            }
                        );

                        if (!photoResponse.ok) {
                            photoWarning =
                                " Your complaint was saved, but its photo could not be uploaded.";
                        }
                    } catch {
                        photoWarning =
                            " Your complaint was saved, but its photo could not be uploaded.";
                    }
                }

                // Display successful submission.
                const box = $("result");

                if (box) {
                    box.replaceChildren();
                    box.style.display = "block";

                    const analysis = data.analysis || {};

                    const heading = document.createElement("h3");
                    heading.textContent = "Report submitted successfully!";
                    box.appendChild(heading);

                    const details = [
                        "Complaint ID: " +
                        (data.complaint_id || "Not provided"),
                        "Category: " +
                        (analysis.category || ai.category || "General"),
                        "Sent to: " +
                        (analysis.responsible_authority || "Relevant authority"),
                        "Priority: " +
                        (analysis.severity || ai.severity || "Not specified")
                    ];

                    details.forEach((item) => {
                        const paragraph = document.createElement("p");
                        paragraph.textContent = item;
                        box.appendChild(paragraph);
                    });

                    const trackingLink = document.createElement("a");
                    trackingLink.href = "Track_report_status.html";
                    trackingLink.textContent = "Track your complaint";
                    box.appendChild(trackingLink);

                    if (photoWarning) {
                        const warning = document.createElement("p");
                        warning.textContent = photoWarning;
                        box.appendChild(warning);
                    }

                    box.scrollIntoView({ behavior: "smooth" });
                }

                status.textContent = "";

            } catch (error) {
                console.error("Complaint submission error:", error);

                setStatus(
                    status,
                    error instanceof TypeError ?
                    "Could not connect to the server. Check your Flask server and website URL." :
                    error.message,
                    true
                );

            } finally {
                if (button) button.disabled = false;
                force = false;
            }
        });
    }

})();
