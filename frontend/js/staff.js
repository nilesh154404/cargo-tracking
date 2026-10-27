/**
 * Superadmin & Internal Staff Backoffice Controller (/staff)
 */
document.addEventListener("DOMContentLoaded", async () => {
  if (!window.authService.requireStaffAuth()) return;

  initStaffTabs();
  await loadStaffStats();
  await loadTenantDirectory();
  await loadCarrierHealth();
  await loadProviderLogs();
});

function initStaffTabs() {
  const tabs = document.querySelectorAll(".staff-nav-btn[data-section]");
  const sections = document.querySelectorAll(".staff-section");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const secId = tab.getAttribute("data-section");
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      sections.forEach(s => {
        s.classList.remove("active");
        if (s.id === `sec-${secId}`) s.classList.add("active");
      });
    });
  });

  document.getElementById("staffLogoutBtn")?.addEventListener("click", () => {
    window.authService.logout();
  });
}

// 1. Platform KPI Overview
async function loadStaffStats() {
  try {
    const stats = await window.apiClient.getAdminStats();
    document.getElementById("statTotalTenants").textContent = stats.total_tenants;
    document.getElementById("statPlatformReqs").textContent = stats.total_platform_requests_month.toLocaleString();
    document.getElementById("statMrrUsd").textContent = `$${stats.mrr_usd.toLocaleString()}`;
    document.getElementById("statSuccessRate").textContent = `${stats.overall_success_rate_percent}%`;
    document.getElementById("statAvgLatency").textContent = `${stats.average_provider_latency_ms} ms`;
    document.getElementById("statTotalShipments").textContent = stats.total_tracked_shipments.toLocaleString();
  } catch (err) {
    console.error("Failed to load admin stats:", err);
  }
}

// 2. Tenant Directory & Quota Adjuster
let allTenants = [];

async function loadTenantDirectory() {
  const tbody = document.getElementById("adminTenantsTbody");
  if (!tbody) return;

  try {
    allTenants = await window.apiClient.getAdminTenants();
    renderTenantTable(allTenants);

    // Search filter
    document.getElementById("tenantSearchInput")?.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase();
      const filtered = allTenants.filter(t => t.name.toLowerCase().includes(q) || t.slug.toLowerCase().includes(q));
      renderTenantTable(filtered);
    });
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:var(--accent-rose); padding:2rem; text-align:center;">Failed to load tenants: ${err.message}</td></tr>`;
  }
}

function renderTenantTable(tenants) {
  const tbody = document.getElementById("adminTenantsTbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (tenants.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="padding:2rem; text-align:center; color:var(--text-muted);">No matching tenants.</td></tr>`;
    return;
  }

  tenants.forEach(t => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <div style="font-weight:700; color:var(--text-main);">${t.name}</div>
        <div style="font-size:0.75rem; color:var(--text-muted); font-family:var(--font-mono);">${t.slug}</div>
      </td>
      <td><span class="badge badge-tier">${t.tier_code.toUpperCase()}</span></td>
      <td>
        <div style="font-size:0.8rem; font-weight:600; margin-bottom:0.25rem;">${t.current_usage.toLocaleString()} / ${t.monthly_quota.toLocaleString()}</div>
        <div class="quota-progress-track" style="width:140px;">
          <div class="quota-progress-fill ${t.quota_usage_pct > 90 ? 'danger' : t.quota_usage_pct > 75 ? 'warning' : ''}" style="width:${Math.min(t.quota_usage_pct, 100)}%;"></div>
        </div>
      </td>
      <td style="font-family:var(--font-mono);">${t.active_api_keys} keys</td>
      <td><span class="badge ${t.is_active ? 'badge-success' : 'badge-danger'}">${t.is_active ? 'ACTIVE' : 'SUSPENDED'}</span></td>
      <td style="font-size:0.8rem; color:var(--text-muted);">${t.created_at ? new Date(t.created_at).toLocaleDateString() : '-'}</td>
      <td>
        <div style="display:flex; gap:0.4rem;">
          <button class="btn btn-secondary btn-sm adjust-quota-btn" data-id="${t.id}" data-name="${t.name}" data-quota="${t.monthly_quota}">Adjust</button>
          <button class="btn btn-outline btn-sm impersonate-btn" data-slug="${t.slug}">Login As</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach Adjust Quota handlers
  document.querySelectorAll(".adjust-quota-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const name = btn.getAttribute("data-name");
      const quota = btn.getAttribute("data-quota");
      openAdjustQuotaModal(id, name, quota);
    });
  });

  // Attach Impersonate handlers
  document.querySelectorAll(".impersonate-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const slug = btn.getAttribute("data-slug");
      if (confirm(`Impersonate tenant "${slug}" and open customer portal?`)) {
        localStorage.setItem(window.APP_CONFIG.STORAGE_KEYS.TENANT_CONTEXT, slug);
        window.location.href = "portal.html";
      }
    });
  });
}

function openAdjustQuotaModal(tenantId, tenantName, currentQuota) {
  const modal = document.getElementById("adjustQuotaModal");
  document.getElementById("modalTenantNameDisplay").textContent = tenantName;
  document.getElementById("adjustQuotaInput").value = currentQuota;
  
  const form = document.getElementById("adjustQuotaForm");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const newQuota = document.getElementById("adjustQuotaInput").value;
    const bonus = document.getElementById("addBonusCreditsInput").value || 0;
    const tier = document.getElementById("changeTierSelect").value;
    const reset = document.getElementById("resetUsageCheck").checked;

    const payload = {};
    if (newQuota) payload.monthly_quota = parseInt(newQuota, 10);
    if (bonus > 0) payload.bonus_credits = parseInt(bonus, 10);
    if (tier) payload.tier_code = tier;
    if (reset) payload.reset_usage = true;

    try {
      await window.apiClient.updateTenantQuota(tenantId, payload);
      window.showToast(`Updated quota for ${tenantName}`, "success");
      modal.classList.remove("active");
      await loadTenantDirectory();
      await loadStaffStats();
    } catch (err) {
      window.showToast(err.message, "error");
    }
  };

  modal.classList.add("active");
}

// 3. Carrier Health SLA Monitor
async function loadCarrierHealth() {
  const grid = document.getElementById("carrierHealthGrid");
  if (!grid) return;

  try {
    const health = await window.apiClient.getProvidersHealth();
    grid.innerHTML = "";

    health.providers.forEach(p => {
      const card = document.createElement("div");
      card.className = "health-card";
      card.innerHTML = `
        <div class="health-card-header">
          <div class="health-provider-name">${p.provider}</div>
          <span class="badge ${p.status === 'HEALTHY' ? 'badge-success' : 'badge-danger'}">${p.status}</span>
        </div>
        <div class="health-metrics-row">
          <span>Transport Mode:</span>
          <span class="badge ${p.mode === 'AIR' ? 'badge-air' : 'badge-sea'}">${p.mode}</span>
        </div>
        <div class="health-metrics-row">
          <span>Integration Class:</span>
          <span style="font-family:var(--font-mono); font-size:0.75rem;">${p.class}</span>
        </div>
        <div class="health-metrics-row">
          <span>SLA Availability:</span>
          <span style="color:var(--accent-emerald); font-weight:700;">99.98%</span>
        </div>
      `;
      grid.appendChild(card);
    });
  } catch (err) {
    grid.innerHTML = `<div style="color:var(--accent-rose);">Failed to load carrier health: ${err.message}</div>`;
  }
}

// 4. Global Provider Execution Logs with cURL Inspector
async function loadProviderLogs() {
  const tbody = document.getElementById("adminLogsContainer");
  if (!tbody) return;

  try {
    const logs = await window.apiClient.getAdminLogs(50);
    tbody.innerHTML = "";

    if (logs.length === 0) {
      tbody.innerHTML = `<div style="padding:2rem; text-align:center; color:var(--text-muted);">No provider logs recorded yet.</div>`;
      return;
    }

    logs.forEach(l => {
      const row = document.createElement("div");
      row.className = "log-row";
      const d = new Date(l.created_at);
      const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

      row.innerHTML = `
        <div style="color:var(--text-muted);">${timeStr}</div>
        <div style="font-weight:700; color:var(--text-main);">${l.tracking_number}</div>
        <div>${l.provider_name}</div>
        <div><span class="badge ${l.status === 'SUCCESS' ? 'badge-success' : l.status === 'FALLBACK' ? 'badge-warning' : 'badge-danger'}">${l.status}</span></div>
        <div>${l.latency_ms ? `${Math.round(l.latency_ms)}ms` : '-'}</div>
        <div style="color:var(--text-muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${l.error_message || 'HTTP 200 OK'}</div>
        <div>
          ${l.request_curl ? `<button class="log-curl-btn view-curl-btn" data-curl="${encodeURIComponent(l.request_curl)}">cURL</button>` : '-'}
        </div>
      `;
      tbody.appendChild(row);
    });

    document.querySelectorAll(".view-curl-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const curl = decodeURIComponent(btn.getAttribute("data-curl"));
        const modal = document.getElementById("curlInspectModal");
        document.getElementById("curlInspectContent").textContent = curl;
        modal.classList.add("active");
      });
    });
  } catch (err) {
    tbody.innerHTML = `<div style="color:var(--accent-rose); padding:2rem;">Failed to load logs: ${err.message}</div>`;
  }
}
