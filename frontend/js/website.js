/**
 * Public Marketing Website & Interactive Tracking Controller
 */
document.addEventListener("DOMContentLoaded", () => {
  initLiveTracker();
  initCodeViewer();
  initPricingSlider();
  initAuthModals();
});

// 1. Interactive Live Cargo Tracker
function initLiveTracker() {
  const input = document.getElementById("heroTrackInput");
  const btn = document.getElementById("heroTrackBtn");
  const resultBox = document.getElementById("trackResultBox");
  const samplePills = document.querySelectorAll(".pill-btn");

  if (!input || !btn) return;

  const performTrack = async (trackingNumber) => {
    if (!trackingNumber) {
      showToast("Please enter an AWB or Container number", "error");
      return;
    }

    btn.disabled = true;
    const originalText = btn.innerHTML;
    btn.innerHTML = `<span class="spinner"></span> Tracking...`;

    try {
      const data = await window.apiClient.track(trackingNumber);
      renderTrackingResult(data);
      if (resultBox) {
        resultBox.classList.add("active");
        resultBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    } catch (err) {
      showToast(err.message || "Could not track shipment", "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  };

  btn.addEventListener("click", () => performTrack(input.value));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") performTrack(input.value);
  });

  samplePills.forEach(pill => {
    pill.addEventListener("click", () => {
      const num = pill.getAttribute("data-number");
      if (num) {
        input.value = num;
        performTrack(num);
      }
    });
  });
}

function renderTrackingResult(shipment) {
  const resultBox = document.getElementById("trackResultBox");
  if (!resultBox) return;

  // Header info - safely extract mode, status, carrier
  const trackingNumber = shipment.tracking_number || "";
  const carrierName = shipment.carrier?.name || shipment.carrier_code || (shipment.carrier?.code) || "Universal Carrier";
  const mode = (shipment.mode || shipment.transport_mode || "SEA").toUpperCase();
  const status = (shipment.status || shipment.current_status || "IN_TRANSIT").toUpperCase();

  const numEl = document.getElementById("resTrackingNumber");
  if (numEl) numEl.textContent = trackingNumber;

  const carrierEl = document.getElementById("resCarrierName");
  if (carrierEl) carrierEl.textContent = carrierName;
  
  const modeBadge = document.getElementById("resModeBadge");
  if (modeBadge) {
    modeBadge.className = `badge badge-${mode.toLowerCase()}`;
    modeBadge.textContent = mode;
  }

  const statusBadge = document.getElementById("resStatusBadge");
  if (statusBadge) {
    const isDelivered = status === "DELIVERED";
    statusBadge.className = `badge ${isDelivered ? 'badge-success' : 'badge-warning'}`;
    statusBadge.textContent = status.replace(/_/g, ' ');
  }

  // Visual Journey Bar
  updateJourneyBar(status);

  // Descending Milestones Timeline (Newest First)
  const timelineContainer = document.getElementById("resTimelineList");
  if (timelineContainer) {
    timelineContainer.innerHTML = "";

    const events = shipment.events || [];
    if (events.length === 0) {
      timelineContainer.innerHTML = `<p style="color:var(--text-muted); font-size:0.9rem; padding:1rem 0;">No milestone events recorded yet.</p>`;
    } else {
      // Ensure descending order (newest first)
      const sortedEvents = [...events].sort((a, b) => {
        const timeA = new Date(a.event_time || a.timestamp || 0).getTime();
        const timeB = new Date(b.event_time || b.timestamp || 0).getTime();
        return timeB - timeA;
      });

      sortedEvents.forEach((ev, idx) => {
        const isLatest = idx === 0;
        const timeVal = ev.event_time || ev.timestamp;
        const d = timeVal ? new Date(timeVal) : new Date();
        const dateStr = !isNaN(d.getTime()) ? d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "-";
        const timeStr = !isNaN(d.getTime()) ? d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true }) : "-";

        const statusName = ev.status_message || ev.status || ev.status_code || "Checkpoint";
        const locationVal = ev.station || ev.location || "";
        const flightOrVessel = ev.flight_info || ev.vessel_name || ev.voyage_flight_number || "";
        const weightVal = ev.weight || ev.gross_weight_kg || "";
        const piecesVal = ev.pieces || "";

        const item = document.createElement("div");
        item.className = `timeline-item ${isLatest ? 'latest' : ''}`;
        item.innerHTML = `
          <div class="timeline-time-col">
            <div class="event-date">${dateStr}</div>
            <div class="event-time">${timeStr}</div>
          </div>
          <div class="timeline-content-col">
            <div class="event-status-line">
              <span class="event-status-name">${statusName}</span>
              ${isLatest ? '<span class="badge badge-success" style="font-size:0.65rem;">LATEST UPDATE</span>' : ''}
            </div>
            ${ev.status_code ? `<div class="event-desc" style="font-size:0.8rem; color:var(--text-muted); font-family:var(--font-mono);">CODE: ${ev.status_code}</div>` : ''}
            <div class="event-meta-tags">
              ${locationVal ? `<span class="meta-tag">📍 ${locationVal}</span>` : ''}
              ${flightOrVessel ? `<span class="meta-tag">🚢/✈️ ${flightOrVessel}</span>` : ''}
              ${weightVal ? `<span class="meta-tag">⚖️ ${weightVal} KG</span>` : ''}
              ${piecesVal ? `<span class="meta-tag">📦 ${piecesVal} PCS</span>` : ''}
            </div>
          </div>
        `;
        timelineContainer.appendChild(item);
      });
    }
  }

  // Ensure result box is active and visible
  resultBox.style.display = "block";
  resultBox.classList.add("active");
  resultBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function updateJourneyBar(status) {
  const steps = ["BOOKED", "GATE_IN", "IN_TRANSIT", "PORT_ARRIVED", "CUSTOMS", "DELIVERED"];
  const connector = document.getElementById("journeyConnector");
  let activeIndex = 2; // Default to IN_TRANSIT

  const s = (status || "").toUpperCase();
  if (s.includes("DELIVER")) activeIndex = 5;
  else if (s.includes("CUSTOMS") || s.includes("CLEAR")) activeIndex = 4;
  else if (s.includes("ARRIV") || s.includes("DISCHARGE")) activeIndex = 3;
  else if (s.includes("TRANSIT") || s.includes("DEPART") || s.includes("SAIL")) activeIndex = 2;
  else if (s.includes("GATE") || s.includes("LOAD")) activeIndex = 1;
  else if (s.includes("BOOK")) activeIndex = 0;

  const pct = (activeIndex / (steps.length - 1)) * 100;
  if (connector) connector.style.width = `${pct}%`;

  for (let i = 0; i < steps.length; i++) {
    const el = document.getElementById(`step-${steps[i]}`);
    if (!el) continue;
    el.classList.remove("completed", "active");
    if (i < activeIndex) {
      el.classList.add("completed");
    } else if (i === activeIndex) {
      el.classList.add("active");
    }
  }
}

// 2. Developer Quickstart Code Viewer
function initCodeViewer() {
  const tabs = document.querySelectorAll(".code-tab");
  const codeBody = document.getElementById("codeBody");
  const copyBtn = document.getElementById("copyCodeBtn");

  const snippets = {
    curl: `curl -X POST "http://localhost:8000/api/v1/track" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: cargotrk_live_your_api_key_here" \\
  -d '{
    "tracking_number": "MSMU6484830",
    "customer_reference": "PO-9842"
  }'`,

    python: `import requests

url = "http://localhost:8000/api/v1/track"
headers = {
    "X-API-Key": "cargotrk_live_your_api_key_here",
    "Content-Type": "application/json"
}
payload = {
    "tracking_number": "MSMU6484830",
    "customer_reference": "PO-9842"
}

response = requests.post(url, json=payload, headers=headers)
data = response.json()
print("Shipment Status:", data["current_status"])
for event in data["events"]:
    print(f"{event['timestamp']} - {event['status']}: {event['description']}")`,

    javascript: `const response = await fetch("http://localhost:8000/api/v1/track", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "cargotrk_live_your_api_key_here"
  },
  body: JSON.stringify({
    tracking_number: "MSMU6484830",
    customer_reference: "PO-9842"
  })
});

const data = await response.json();
console.log("Current Status:", data.current_status);
console.log("Timeline Events:", data.events);`,

    go: `package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
)

func main() {
	payload, _ := json.Marshal(map[string]string{
		"tracking_number": "MSMU6484830",
	})

	req, _ := http.NewRequest("POST", "http://localhost:8000/api/v1/track", bytes.NewBuffer(payload))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-API-Key", "cargotrk_live_your_api_key_here")

	client := &http.Client{}
	resp, _ := client.Do(req)
	defer resp.Body.Close()
	fmt.Println("Tracking response status:", resp.Status)
}`
  };

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      const lang = tab.getAttribute("data-lang");
      if (codeBody && snippets[lang]) {
        codeBody.textContent = snippets[lang];
      }
    });
  });

  if (copyBtn && codeBody) {
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(codeBody.textContent);
      showToast("Code copied to clipboard!", "success");
    });
  }
}

// 3. Interactive Pricing Volume Slider
function initPricingSlider() {
  const slider = document.getElementById("volumeSlider");
  const volumeVal = document.getElementById("volumeValue");
  const costVal = document.getElementById("estCostValue");
  const tierRec = document.getElementById("recTierBadge");

  if (!slider) return;

  const updateEstimate = () => {
    const val = parseInt(slider.value, 10);
    volumeVal.textContent = val.toLocaleString();

    let cost = 0;
    let tier = "Developer (Free)";
    if (val <= 100) {
      cost = 0;
      tier = "Developer (Free)";
    } else if (val <= 2500) {
      cost = 199;
      tier = "Growth Plan";
    } else if (val <= 15000) {
      cost = 699;
      tier = "Business Plan";
    } else {
      cost = 2499;
      tier = "Enterprise Custom";
    }

    if (costVal) costVal.textContent = `$${cost}/mo`;
    if (tierRec) tierRec.textContent = tier;
  };

  slider.addEventListener("input", updateEstimate);
  updateEstimate();
}

// 4. Auth Modals
function initAuthModals() {
  const loginModal = document.getElementById("loginModal");
  const registerModal = document.getElementById("registerModal");

  // Global modal opener buttons
  document.querySelectorAll("[data-open-modal='login']").forEach(btn => {
    btn.addEventListener("click", () => openModal(loginModal));
  });
  document.querySelectorAll("[data-open-modal='register']").forEach(btn => {
    btn.addEventListener("click", () => openModal(registerModal));
  });

  // Close buttons
  document.querySelectorAll(".modal-close, .modal-backdrop").forEach(el => {
    el.addEventListener("click", (e) => {
      if (e.target === el) {
        closeAllModals();
      }
    });
  });

  // Login Form Submission
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = document.getElementById("loginEmail").value;
      const pass = document.getElementById("loginPassword").value;
      const isStaff = document.getElementById("loginAsStaffCheck")?.checked;

      try {
        await window.authService.login(email, pass);
        showToast("Login successful!", "success");
        closeAllModals();
        setTimeout(() => {
          window.location.href = isStaff ? "staff.html" : "portal.html";
        }, 600);
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // Register Form Submission
  const regForm = document.getElementById("registerForm");
  if (regForm) {
    regForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        organization_name: document.getElementById("regOrgName").value,
        slug: document.getElementById("regOrgSlug").value,
        admin_email: document.getElementById("regEmail").value,
        admin_password: document.getElementById("regPassword").value,
        subscription_tier: document.getElementById("regTier").value || "growth"
      };

      try {
        const res = await window.authService.registerOrganization(payload);
        showToast("Organization onboarded successfully!", "success");
        // Show newly generated API key card in modal
        document.getElementById("regFormFields").style.display = "none";
        const successBox = document.getElementById("regSuccessBox");
        successBox.style.display = "block";
        document.getElementById("newApiKeyDisplay").textContent = res.api_key?.key || "cargotrk_live_...";
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  // Check URL params for immediate modal trigger
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("auth") === "login") openModal(loginModal);
  if (urlParams.get("auth") === "register") openModal(registerModal);
}

function openModal(modal) {
  if (modal) modal.classList.add("active");
}
function closeAllModals() {
  document.querySelectorAll(".modal-backdrop").forEach(m => m.classList.remove("active"));
}

function showToast(message, type = "info") {
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span> <div>${message}</div>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4500);
}
window.showToast = showToast;
