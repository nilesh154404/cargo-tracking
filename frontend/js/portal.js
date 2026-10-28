/**
 * Multi-Tenant Customer Portal Controller (/app)
 */
document.addEventListener("DOMContentLoaded", async () => {
  // Ensure authentication
  if (!window.authService.requirePortalAuth()) return;

  initPortalNavigation();
  await loadTenantProfileAndQuota();
  await loadDashboardShipments();
  initPortalTracking();
  initBatchTracking();
  initApiKeyManager();
  initBillingCenter();
});

// 1. Navigation & View Switching
function initPortalNavigation() {
  const navBtns = document.querySelectorAll(".nav-item-btn[data-view]");
  const views = document.querySelectorAll(".portal-view");

  navBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const viewId = btn.getAttribute("data-view");
      navBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      views.forEach(v => {
        v.classList.remove("active");
        if (v.id === `view-${viewId}`) {
          v.classList.add("active");
        }
      });
    });
  });

  // Logout button
  document.getElementById("portalLogoutBtn")?.addEventListener("click", () => {
    window.authService.logout();
  });
}

// 2. Load Tenant Context & Quota Gauge
async function loadTenantProfileAndQuota() {
  try {
    const usage = await window.apiClient.getUsage();
    
    // Header elements
    const nameEl = document.getElementById("tenantNameDisplay");
    const tierBadge = document.getElementById("tenantTierBadge");
    if (nameEl) nameEl.textContent = usage.tenant_name;
    if (tierBadge) tierBadge.textContent = `${usage.tier_code.toUpperCase()} PLAN`;

    // Quota Gauge
    const usageText = document.getElementById("quotaTextDisplay");
    const progressFill = document.getElementById("quotaProgressBar");
    
    if (usageText) {
      usageText.textContent = `${usage.current_usage.toLocaleString()} / ${usage.monthly_quota.toLocaleString()} Credits (${usage.usage_percentage}%)`;
    }
    if (progressFill) {
      progressFill.style.width = `${Math.min(usage.usage_percentage, 100)}%`;
      progressFill.className = "quota-progress-fill";
      if (usage.usage_percentage > 90) progressFill.classList.add("danger");
      else if (usage.usage_percentage > 75) progressFill.classList.add("warning");
    }

    // Dashboard Metric Cards
    document.getElementById("metricCreditsRemaining").textContent = Math.max(0, usage.monthly_quota - usage.current_usage).toLocaleString();
    document.getElementById("metricMonthlyQuota").textContent = usage.monthly_quota.toLocaleString();
  } catch (err) {
    console.error("Failed to load quota:", err);
  }
}

// 3. Load Recent Shipments for Dashboard
async function loadDashboardShipments() {
  const tbody = document.getElementById("dashboardShipmentTbody");
  if (!tbody) return;

  try {
    const shipments = await window.apiClient.getShipments(25);
    
    // Update metric counters
    const active = shipments.filter(s => s.status !== "DELIVERED").length;
    const delivered = shipments.filter(s => s.status === "DELIVERED").length;
    document.getElementById("metricActiveShipments").textContent = active;
    document.getElementById("metricDeliveredCount").textContent = delivered;

    tbody.innerHTML = "";
    if (shipments.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:2rem; color:var(--text-muted);">No tracked shipments recorded in this workspace.</td></tr>`;
      return;
    }

    shipments.forEach(s => {
      const tr = document.createElement("tr");
      const isAir = s.mode === "AIR";
      const isDelivered = s.status === "DELIVERED";
      const updatedStr = s.last_event_time ? new Date(s.last_event_time).toLocaleDateString() : "-";

      tr.innerHTML = `
        <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-main);">${s.tracking_number}</td>
        <td><span class="badge ${isAir ? 'badge-air' : 'badge-sea'}">${s.mode}</span></td>
        <td>${s.carrier_code || 'Universal'}</td>
        <td>${s.customer_reference || '-'}</td>
        <td><span class="badge ${isDelivered ? 'badge-success' : 'badge-warning'}">${s.status || 'IN TRANSIT'}</span></td>
        <td>${s.current_location || '-'}</td>
        <td style="font-size:0.8rem; color:var(--text-muted);">${updatedStr}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--accent-rose); padding:2rem;">Failed to load shipments: ${err.message}</td></tr>`;
  }
}

// 4. Live Tracking in Customer Portal
function initPortalTracking() {
  const input = document.getElementById("portalTrackInput");
  const btn = document.getElementById("portalTrackBtn");
  const resultCard = document.getElementById("portalTrackResult");

  if (!input || !btn) return;

  btn.addEventListener("click", async () => {
    const num = input.value.trim();
    if (!num) return;

    btn.disabled = true;
    btn.textContent = "Querying Live APIs...";

    try {
      const data = await window.apiClient.track(num);
      renderPortalTrackingDetails(data);
      resultCard.style.display = "block";
      // Refresh quota meter
      await loadTenantProfileAndQuota();
    } catch (err) {
      window.showToast(err.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Track Shipment";
    }
  });
}

function renderPortalTrackingDetails(shipment) {
  const trackingNumber = shipment.tracking_number || "";
  const carrierName = shipment.carrier?.name || shipment.carrier_code || (shipment.carrier?.code) || "Universal Carrier";
  const status = (shipment.status || shipment.current_status || "IN_TRANSIT").toUpperCase();

  const numEl = document.getElementById("portalResNum");
  if (numEl) numEl.textContent = trackingNumber;

  const carrierEl = document.getElementById("portalResCarrier");
  if (carrierEl) carrierEl.textContent = carrierName;

  const statusEl = document.getElementById("portalResStatus");
  if (statusEl) statusEl.textContent = status.replace(/_/g, ' ');

  const timeline = document.getElementById("portalResTimeline");
  if (!timeline) return;
  timeline.innerHTML = "";

  const events = shipment.events || [];
  // Descending sort (newest first)
  const sorted = [...events].sort((a, b) => {
    const timeA = new Date(a.event_time || a.timestamp || 0).getTime();
    const timeB = new Date(b.event_time || b.timestamp || 0).getTime();
    return timeB - timeA;
  });

  sorted.forEach((ev, idx) => {
    const isLatest = idx === 0;
    const timeVal = ev.event_time || ev.timestamp;
    const d = timeVal ? new Date(timeVal) : new Date();
    const dateStr = !isNaN(d.getTime()) ? d.toLocaleDateString() : '-';
    const timeStr = !isNaN(d.getTime()) ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-';

    const statusText = ev.status_message || ev.status || ev.status_code || "Checkpoint";
    const locationText = ev.station || ev.location || "";
    const flightOrVessel = ev.flight_info || ev.vessel_name || ev.voyage_flight_number || "";
    const weightVal = ev.weight || "";

    const item = document.createElement("div");
    item.className = `timeline-item ${isLatest ? 'latest' : ''}`;
    item.innerHTML = `
      <div class="timeline-time-col">
        <div class="event-date">${dateStr}</div>
        <div class="event-time">${timeStr}</div>
      </div>
      <div class="timeline-content-col">
        <div class="event-status-line">
          <span class="event-status-name">${statusText}</span>
          ${isLatest ? '<span class="badge badge-success">NEWEST</span>' : ''}
        </div>
        ${ev.status_code ? `<div class="event-desc" style="font-size:0.8rem; color:var(--text-muted); font-family:var(--font-mono);">CODE: ${ev.status_code}</div>` : ''}
        <div class="event-meta-tags">
          ${locationText ? `<span class="meta-tag">📍 ${locationText}</span>` : ''}
          ${flightOrVessel ? `<span class="meta-tag">🚢/✈️ ${flightOrVessel}</span>` : ''}
          ${weightVal ? `<span class="meta-tag">⚖️ ${weightVal} KG</span>` : ''}
        </div>
      </div>
    `;
    timeline.appendChild(item);
  });
}

// 5. Batch Ingestion & CSV Exporter
let lastBatchResults = [];

function initBatchTracking() {
  const fileInput = document.getElementById("batchFileInput");
  const dropzone = document.getElementById("batchDropzone");
  const processBtn = document.getElementById("processBatchBtn");
  const exportBtn = document.getElementById("exportBatchCsvBtn");
  const textarea = document.getElementById("batchManualText");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) handleBatchFile(file);
    });
  }

  processBtn?.addEventListener("click", async () => {
    const raw = textarea.value.trim();
    if (!raw) {
      window.showToast("Please enter tracking numbers or upload a file", "error");
      return;
    }

    const lines = raw.split("\n").map(l => l.trim()).filter(Boolean);
    const shipments = lines.map(line => {
      const parts = line.split(",").map(p => p.trim());
      return {
        tracking_number: parts[0],
        carrier_code: parts[1] || null,
        customer_reference: parts[2] || "Batch-Upload"
      };
    });

    processBtn.disabled = true;
    processBtn.textContent = `Processing ${shipments.length} shipments...`;

    try {
      const res = await window.apiClient.batchTrack(shipments);
      lastBatchResults = res.results || [];
      renderBatchResults(lastBatchResults);
      if (exportBtn) exportBtn.style.display = "inline-flex";
      window.showToast(`Batch processed: ${res.successful} success, ${res.failed} failed`, "success");
      await loadTenantProfileAndQuota();
    } catch (err) {
      window.showToast(err.message, "error");
    } finally {
      processBtn.disabled = false;
      processBtn.textContent = "Execute Batch Track";
    }
  });

  exportBtn?.addEventListener("click", () => {
    if (!lastBatchResults.length) return;
    exportBatchToCsv(lastBatchResults);
  });
}

function handleBatchFile(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    document.getElementById("batchManualText").value = text;
    window.showToast(`Loaded ${file.name}`, "info");
  };
  reader.readAsText(file);
}

function renderBatchResults(results) {
  const container = document.getElementById("batchResultsContainer");
  const tbody = document.getElementById("batchResultsTbody");
  if (!container || !tbody) return;

  container.style.display = "block";
  tbody.innerHTML = "";

  results.forEach(r => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-main);">${r.tracking_number}</td>
      <td><span class="badge ${r.transport_mode === 'AIR' ? 'badge-air' : 'badge-sea'}">${r.transport_mode || '-'}</span></td>
      <td>${r.carrier_code || '-'}</td>
      <td><span class="badge ${r.current_status === 'DELIVERED' ? 'badge-success' : 'badge-warning'}">${r.current_status || 'PROCESSED'}</span></td>
      <td><span class="badge ${r.status === 'SUCCESS' ? 'badge-success' : 'badge-danger'}">${r.status}</span></td>
      <td style="font-size:0.8rem; color:var(--text-muted);">${r.error || 'OK'}</td>
    `;
    tbody.appendChild(tr);
  });
}

function exportBatchToCsv(results) {
  let csv = "Tracking Number,Mode,Carrier,Status,Result,Error\n";
  results.forEach(r => {
    csv += `"${r.tracking_number}","${r.transport_mode || ''}","${r.carrier_code || ''}","${r.current_status || ''}","${r.status}","${r.error || ''}"\n`;
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `cargo_tracking_report_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// 6. Developer API Key Manager
function initApiKeyManager() {
  loadApiKeysList();

  const createKeyBtn = document.getElementById("openCreateKeyModalBtn");
  const modal = document.getElementById("createKeyModal");
  const form = document.getElementById("createKeyForm");

  createKeyBtn?.addEventListener("click", () => modal?.classList.add("active"));

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("newKeyName").value;

    try {
      const res = await window.apiClient.createApiKey(name);
      modal?.classList.remove("active");
      
      // Open secret reveal dialog
      const revealModal = document.getElementById("keyRevealModal");
      document.getElementById("secretKeyDisplay").textContent = res.key;
      revealModal?.classList.add("active");

      await loadApiKeysList();
    } catch (err) {
      window.showToast(err.message, "error");
    }
  });

  document.getElementById("copySecretKeyBtn")?.addEventListener("click", () => {
    const text = document.getElementById("secretKeyDisplay").textContent;
    navigator.clipboard.writeText(text);
    window.showToast("API Key copied to clipboard!", "success");
  });
}

async function loadApiKeysList() {
  const tbody = document.getElementById("apiKeysTbody");
  if (!tbody) return;

  try {
    const keys = await window.apiClient.getApiKeys();
    tbody.innerHTML = "";

    if (keys.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:2rem; color:var(--text-muted);">No active API keys found.</td></tr>`;
      return;
    }

    keys.forEach(k => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight:700; color:var(--text-main);">${k.name}</td>
        <td style="font-family:var(--font-mono); color:var(--accent-cyan);">${k.prefix}...</td>
        <td><span class="badge ${k.is_active ? 'badge-success' : 'badge-danger'}">${k.is_active ? 'ACTIVE' : 'REVOKED'}</span></td>
        <td style="font-size:0.8rem; color:var(--text-muted);">${new Date(k.created_at).toLocaleDateString()}</td>
        <td style="font-size:0.8rem; color:var(--text-muted);">${k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : 'Never'}</td>
        <td>
          ${k.is_active ? `<button class="btn btn-danger btn-sm revoke-key-btn" data-key-id="${k.id}">Revoke</button>` : '<span style="color:var(--text-muted); font-size:0.75rem;">REVOKED</span>'}
        </td>
      `;
      tbody.appendChild(tr);
    });

    document.querySelectorAll(".revoke-key-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-key-id");
        if (confirm("Are you sure you want to revoke this API key? Applications using it will stop working immediately.")) {
          await window.apiClient.revokeApiKey(id);
          window.showToast("API key revoked", "info");
          loadApiKeysList();
        }
      });
    });
  } catch (err) {
    console.error("Failed to load keys:", err);
  }
}

// 7. Subscription & Billing Center
function initBillingCenter() {
  const upgradeBtn = document.getElementById("openUpgradeModalBtn");
  const modal = document.getElementById("upgradeModal");

  upgradeBtn?.addEventListener("click", () => modal?.classList.add("active"));

  document.querySelectorAll(".select-tier-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const tier = btn.getAttribute("data-tier");
      try {
        await window.apiClient.upgradePlan(tier);
        window.showToast(`Plan successfully upgraded to ${tier.toUpperCase()}!`, "success");
        modal?.classList.remove("active");
        await loadTenantProfileAndQuota();
      } catch (err) {
        window.showToast(err.message, "error");
      }
    });
  });
}
