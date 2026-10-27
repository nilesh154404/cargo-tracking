"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  getAdminPlatformStats,
  listAdminTenants,
  onboardNewTenant,
  updateTenantQuota,
  impersonateTenant,
  getCarrierHealthSla,
  getProviderExecutionLogs,
  getAdminUsageLogs,
  loginUser,
  STORAGE_KEYS
} from "@/lib/api";

export default function SuperadminStaffBackofficePage() {
  const [activeTab, setActiveTab] = useState("tenants");
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  // Staff Login Form State
  const [loginEmail, setLoginEmail] = useState("superadmin@cargotrack.io");
  const [loginPassword, setLoginPassword] = useState("SuperAdmin@2026!Cargo");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // Platform Data
  const [stats, setStats] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [carriers, setCarriers] = useState([]);
  const [logs, setLogs] = useState([]);
  const [usageRecords, setUsageRecords] = useState([]);
  const [usageRecordsLoading, setUsageRecordsLoading] = useState(false);
  const [adminFilterTenant, setAdminFilterTenant] = useState("");
  const [adminFilterSearch, setAdminFilterSearch] = useState("");
  const [adminFilterMode, setAdminFilterMode] = useState("ALL");

  // Onboard New Tenant Modal State
  const [onboardModalOpen, setOnboardModalOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState("");
  const [newSlug, setNewSlug] = useState("");
  const [newTier, setNewTier] = useState("growth");
  const [newAdminEmail, setNewAdminEmail] = useState("");
  const [newAdminPassword, setNewAdminPassword] = useState("Admin@2026!Cargo");
  const [newAdminName, setNewAdminName] = useState("");
  const [newQuota, setNewQuota] = useState("");
  const [newRpm, setNewRpm] = useState("");
  const [newAllowOverage, setNewAllowOverage] = useState(false);
  const [onboardLoading, setOnboardLoading] = useState(false);
  const [onboardError, setOnboardError] = useState("");
  const [onboardSuccessData, setOnboardSuccessData] = useState(null);

  // Quota Adjuster Modal State
  const [quotaModalOpen, setQuotaModalOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState(null);
  const [bonusCredits, setBonusCredits] = useState("5000");
  const [resetUsage, setResetUsage] = useState(false);
  const [tenantStatusActive, setTenantStatusActive] = useState(true);
  const [quotaLoading, setQuotaLoading] = useState(false);

  // cURL Inspect Modal State
  const [curlModalOpen, setCurlModalOpen] = useState(false);
  const [selectedLog, setSelectedLog] = useState(null);

  useEffect(() => {
    checkStaffAuth();
  }, []);

  const checkStaffAuth = async () => {
    if (typeof window === "undefined") return;
    const token = localStorage.getItem(STORAGE_KEYS.STAFF_TOKEN) || localStorage.getItem(STORAGE_KEYS.TOKEN);
    if (!token) {
      setLoading(false);
      setIsAuthenticated(false);
      return;
    }

    try {
      const statsData = await getAdminPlatformStats();
      setStats(statsData);
      setIsAuthenticated(true);
      loadAdminData();
    } catch (err) {
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  const handleStaffLogin = async (e) => {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError("");

    try {
      const data = await loginUser(loginEmail, loginPassword);
      if (data.user?.role !== "SUPER_ADMIN" && data.user?.role !== "ADMIN") {
        throw new Error("Access denied. Superadmin credentials required.");
      }
      localStorage.setItem(STORAGE_KEYS.STAFF_TOKEN, data.access_token);
      setIsAuthenticated(true);
      loadAdminData();
    } catch (err) {
      setLoginError(err.message || "Invalid superadmin credentials.");
    } finally {
      setLoginLoading(false);
    }
  };

  const loadAdminData = async () => {
    try {
      const [statsData, tenantsData, carriersData, logsData, usageLogsData] = await Promise.all([
        getAdminPlatformStats().catch(() => null),
        listAdminTenants().catch(() => []),
        getCarrierHealthSla().catch(() => []),
        getProviderExecutionLogs(50).catch(() => []),
        getAdminUsageLogs({ limit: 100 }).catch(() => []),
      ]);

      if (statsData) setStats(statsData);
      setTenants(tenantsData);
      setCarriers(carriersData);
      setLogs(logsData);
      setUsageRecords(usageLogsData);
    } catch (err) {
      console.error("Admin data load error:", err);
    }
  };

  const handleLoadAdminUsageLogs = async (tenantId = adminFilterTenant, mode = adminFilterMode, search = adminFilterSearch) => {
    setUsageRecordsLoading(true);
    try {
      const data = await getAdminUsageLogs({
        limit: 100,
        tenant_id: tenantId ? parseInt(tenantId) : null,
        mode: mode === "ALL" ? "" : mode,
        search: search.trim()
      });
      setUsageRecords(data || []);
    } catch (err) {
      console.warn("Failed to load admin usage logs:", err);
    } finally {
      setUsageRecordsLoading(false);
    }
  };

  const handleOnboardTenant = async (e) => {
    e.preventDefault();
    setOnboardLoading(true);
    setOnboardError("");

    try {
      const payload = {
        name: newOrgName.trim(),
        slug: newSlug.trim().toLowerCase(),
        tier_code: newTier,
        admin_email: newAdminEmail.trim().toLowerCase(),
        admin_password: newAdminPassword,
        admin_name: newAdminName.trim() || undefined,
        monthly_quota: newQuota ? parseInt(newQuota, 10) : undefined,
        rate_limit_rpm: newRpm ? parseInt(newRpm, 10) : undefined,
        allow_overage: newAllowOverage,
      };

      const res = await onboardNewTenant(payload);
      setOnboardSuccessData(res);
      // Reload tenants
      const updated = await listAdminTenants();
      setTenants(updated);
    } catch (err) {
      setOnboardError(err.message || "Failed to onboard new tenant.");
    } finally {
      setOnboardLoading(false);
    }
  };

  const handleUpdateQuota = async (e) => {
    e.preventDefault();
    if (!selectedTenant) return;
    setQuotaLoading(true);

    try {
      await updateTenantQuota(selectedTenant.id, {
        bonus_credits: bonusCredits ? parseInt(bonusCredits, 10) : undefined,
        reset_usage: resetUsage,
        is_active: tenantStatusActive,
      });

      alert(`Quota updated for tenant '${selectedTenant.name}'!`);
      setQuotaModalOpen(false);
      const updated = await listAdminTenants();
      setTenants(updated);
    } catch (err) {
      alert(err.message || "Failed to update tenant quota.");
    } finally {
      setQuotaLoading(false);
    }
  };

  const handleImpersonate = async (tenantId) => {
    try {
      const res = await impersonateTenant(tenantId);
      localStorage.setItem(STORAGE_KEYS.TOKEN, res.access_token);
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify({ email: res.user_email, role: "ADMIN" }));
      localStorage.setItem(STORAGE_KEYS.TENANT, JSON.stringify({ slug: res.tenant_slug, name: res.tenant_name }));
      window.open("/portal", "_blank");
    } catch (err) {
      alert(err.message || "Failed to impersonate tenant.");
    }
  };

  const handleStaffLogout = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEYS.STAFF_TOKEN);
    }
    setIsAuthenticated(false);
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-primary)" }}>
        <span className="spinner" style={{ width: "2rem", height: "2rem", color: "var(--accent-blue)" }} />
      </div>
    );
  }

  // If Not Authenticated, Render Dedicated Staff Sign In Form
  if (!isAuthenticated) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f8fafc", padding: "1.5rem" }}>
        <div className="card" style={{ maxWidth: "440px", width: "100%", padding: "2.5rem", boxShadow: "var(--shadow-xl)" }}>
          <div style={{ textAlign: "center", marginBottom: "2rem" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>🛡️</div>
            <h1 style={{ fontSize: "1.5rem", fontWeight: "800", color: "#0f172a" }}>Superadmin &amp; Staff Backoffice</h1>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>Platform Operations &amp; Multi-Tenant Control</p>
          </div>

          <form onSubmit={handleStaffLogin}>
            {loginError && (
              <div style={{ padding: "0.75rem", background: "#fef2f2", color: "#b91c1c", borderRadius: "6px", fontSize: "0.85rem", marginBottom: "1rem" }}>
                {loginError}
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Superadmin Email</label>
              <input
                type="email"
                className="form-input"
                required
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Password</label>
              <input
                type="password"
                className="form-input"
                required
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
              />
            </div>

            <button type="submit" disabled={loginLoading} className="btn btn-primary" style={{ width: "100%", height: "46px", marginTop: "1.25rem" }}>
              {loginLoading ? "Verifying..." : "Sign In to Backoffice"}
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: "1.5rem" }}>
            <Link href="/" style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              ← Return to Public Website
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-primary)" }}>
      {/* Sidebar */}
      <aside style={{ width: "260px", background: "#ffffff", borderRight: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "1.5rem", borderBottom: "1px solid var(--border-subtle)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1.2rem", fontWeight: "800", color: "#0f172a" }}>
            <span>🛡️</span>
            <span>CargoTrk <span style={{ color: "var(--accent-rose)", fontSize: "0.85rem" }}>STAFF</span></span>
          </div>
          <div style={{ marginTop: "0.5rem", fontSize: "0.78rem", color: "var(--text-muted)" }}>
            Root Platform Administration
          </div>
        </div>

        <nav style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.35rem", flex: 1 }}>
          {[
            { id: "tenants", label: "Tenant Directory & Onboarding", icon: "🏢" },
            { id: "usagelogs", label: "Global Usage & Audit History", icon: "📜" },
            { id: "carriers", label: "Carrier Network Health SLA", icon: "🌐" },
            { id: "telemetry", label: "Global Provider Logs & cURL", icon: "📡" },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setActiveTab(item.id);
                if (item.id === "usagelogs") {
                  handleLoadAdminUsageLogs();
                }
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                padding: "0.75rem 1rem",
                borderRadius: "var(--radius-md)",
                border: "none",
                background: activeTab === item.id ? "#eff6ff" : "transparent",
                color: activeTab === item.id ? "var(--accent-blue)" : "var(--text-secondary)",
                fontWeight: activeTab === item.id ? "700" : "500",
                fontSize: "0.9rem",
                textAlign: "left",
                cursor: "pointer"
              }}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div style={{ padding: "1.25rem", borderTop: "1px solid var(--border-subtle)" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
            Superadmin Session Active
          </div>
          <button onClick={handleStaffLogout} className="btn btn-secondary btn-sm" style={{ width: "100%" }}>
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Top Header */}
        <header style={{
          height: "72px",
          background: "#ffffff",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 2rem",
          boxShadow: "var(--shadow-sm)"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <h2 style={{ fontSize: "1.25rem", fontWeight: "700", color: "#0f172a" }}>
              {activeTab === "tenants" && "Enterprise Tenants & Onboarding"}
              {activeTab === "usagelogs" && "Global Tenant Usage & Tracking History"}
              {activeTab === "carriers" && "Carrier Health SLA & Dynamic Routing"}
              {activeTab === "telemetry" && "Provider Telemetry & Debugger"}
            </h2>
            <span className="badge badge-danger">SUPERADMIN PRIVILEGE</span>
          </div>

          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button
              onClick={() => { setOnboardModalOpen(true); setOnboardSuccessData(null); }}
              className="btn btn-primary btn-sm"
            >
              + Onboard New Tenant
            </button>
            <Link href="/" target="_blank" className="btn btn-secondary btn-sm">
              Public Website ↗
            </Link>
          </div>
        </header>

        {/* Content Body */}
        <div style={{ padding: "2rem", flex: 1 }}>
          {/* Top Platform KPI Cockpit Cards */}
          {stats && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1.25rem", marginBottom: "2rem" }}>
              <div className="card">
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: "600" }}>Total Active Tenants</div>
                <div style={{ fontSize: "1.8rem", fontWeight: "800", color: "#0f172a", margin: "0.25rem 0" }}>{stats.total_tenants}</div>
                <div style={{ fontSize: "0.78rem", color: "var(--accent-emerald)" }}>Enterprise Multi-Tenant</div>
              </div>

              <div className="card">
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: "600" }}>Monthly Platform Requests</div>
                <div style={{ fontSize: "1.8rem", fontWeight: "800", color: "var(--accent-blue)", margin: "0.25rem 0" }}>
                  {(stats.total_platform_requests_month || 0).toLocaleString()}
                </div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Across All Organizations</div>
              </div>

              <div className="card">
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: "600" }}>Est. Monthly Recurring Revenue</div>
                <div style={{ fontSize: "1.8rem", fontWeight: "800", color: "var(--accent-emerald)", margin: "0.25rem 0" }}>
                  ${(stats.mrr_usd || 0).toLocaleString()}
                </div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Based on active plan tiers</div>
              </div>

              <div className="card">
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: "600" }}>Carrier Success SLA</div>
                <div style={{ fontSize: "1.8rem", fontWeight: "800", color: "var(--accent-cyan)", margin: "0.25rem 0" }}>
                  {stats.overall_success_rate_percent}%
                </div>
                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Avg Latency: {stats.average_provider_latency_ms}ms</div>
              </div>
            </div>
          )}

          {/* TAB 1: TENANT MANAGEMENT DIRECTORY */}
          {activeTab === "tenants" && (
            <div className="card" style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: "700" }}>Enterprise Tenant Organizations</h3>
                  <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                    Manage quotas, reset usage credits, impersonate tenant accounts, and provision new subscriptions.
                  </p>
                </div>
                <button
                  onClick={() => { setOnboardModalOpen(true); setOnboardSuccessData(null); }}
                  className="btn btn-primary btn-sm"
                >
                  + Onboard New Tenant
                </button>
              </div>

              <div className="table-wrapper" style={{ border: "none" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Organization</th>
                      <th>Slug</th>
                      <th>Subscription Tier</th>
                      <th>Quota Usage</th>
                      <th>Active Keys</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tenants.map((t) => (
                      <tr key={t.id}>
                        <td>
                          <div style={{ fontWeight: "700", color: "var(--text-main)" }}>{t.name}</div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>ID: {t.id}</div>
                        </td>
                        <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem" }}>{t.slug}</td>
                        <td>
                          <span className="badge badge-air">{(t.tier_code || "GROWTH").toUpperCase()}</span>
                        </td>
                        <td style={{ minWidth: "160px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                            <span>{t.current_usage} / {t.monthly_quota}</span>
                            <span>{t.quota_usage_pct}%</span>
                          </div>
                          <div style={{ height: "5px", background: "var(--bg-secondary)", borderRadius: "3px", overflow: "hidden" }}>
                            <div style={{
                              height: "100%",
                              width: `${Math.min(t.quota_usage_pct, 100)}%`,
                              background: t.quota_usage_pct > 90 ? "var(--accent-rose)" : "var(--accent-blue)"
                            }} />
                          </div>
                        </td>
                        <td><strong>{t.active_api_keys}</strong> active</td>
                        <td>
                          <span className={`badge ${t.is_active ? "badge-success" : "badge-danger"}`}>
                            {t.is_active ? "ACTIVE" : "SUSPENDED"}
                          </span>
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: "0.4rem" }}>
                            <button
                              onClick={() => {
                                setSelectedTenant(t);
                                setTenantStatusActive(t.is_active);
                                setQuotaModalOpen(true);
                              }}
                              className="btn btn-secondary btn-sm"
                            >
                              Adjust Quota
                            </button>
                            <button
                              onClick={() => handleImpersonate(t.id)}
                              className="btn btn-outline btn-sm"
                            >
                              Impersonate ↗
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB: GLOBAL USAGE & AUDIT HISTORY */}
          {activeTab === "usagelogs" && (
            <div className="card" style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
                <div>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: "700" }}>Global Multi-Tenant Usage &amp; Tracking History</h3>
                  <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                    Real-time audit log of all tracking queries, credits consumed, and carrier routing decisions across tenants.
                  </p>
                </div>
                <button
                  onClick={() => handleLoadAdminUsageLogs(adminFilterTenant, adminFilterMode, adminFilterSearch)}
                  className="btn btn-outline btn-sm"
                  disabled={usageRecordsLoading}
                >
                  {usageRecordsLoading ? "Refreshing..." : "🔄 Refresh"}
                </button>
              </div>

              {/* Filters Toolbar */}
              <div style={{ padding: "1rem 1.5rem", background: "#f8fafc", borderBottom: "1px solid var(--border-subtle)", display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flex: "1 1 300px", maxWidth: "420px" }}>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Search tracking #, carrier, provider..."
                    value={adminFilterSearch}
                    onChange={(e) => setAdminFilterSearch(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        handleLoadAdminUsageLogs(adminFilterTenant, adminFilterMode, e.target.value);
                      }
                    }}
                    style={{ fontSize: "0.85rem", height: "38px" }}
                  />
                  <button
                    onClick={() => handleLoadAdminUsageLogs(adminFilterTenant, adminFilterMode, adminFilterSearch)}
                    className="btn btn-secondary btn-sm"
                    style={{ height: "38px" }}
                  >
                    Search
                  </button>
                </div>

                <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
                  {/* Tenant Select */}
                  <select
                    className="form-select"
                    value={adminFilterTenant}
                    onChange={(e) => {
                      setAdminFilterTenant(e.target.value);
                      handleLoadAdminUsageLogs(e.target.value, adminFilterMode, adminFilterSearch);
                    }}
                    style={{ fontSize: "0.82rem", height: "38px" }}
                  >
                    <option value="">All Organizations</option>
                    {tenants.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.slug})
                      </option>
                    ))}
                  </select>

                  {/* Mode Filter */}
                  <div style={{ display: "flex", background: "#ffffff", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-md)", padding: "2px" }}>
                    {[
                      { id: "ALL", label: "All" },
                      { id: "SEA", label: "🚢 Sea" },
                      { id: "AIR", label: "✈️ Air" },
                    ].map((m) => (
                      <button
                        key={m.id}
                        onClick={() => {
                          setAdminFilterMode(m.id);
                          handleLoadAdminUsageLogs(adminFilterTenant, m.id, adminFilterSearch);
                        }}
                        style={{
                          padding: "0.35rem 0.65rem",
                          border: "none",
                          borderRadius: "var(--radius-sm)",
                          fontSize: "0.82rem",
                          fontWeight: adminFilterMode === m.id ? "700" : "500",
                          background: adminFilterMode === m.id ? "var(--accent-blue)" : "transparent",
                          color: adminFilterMode === m.id ? "#ffffff" : "var(--text-secondary)",
                          cursor: "pointer"
                        }}
                      >
                        {m.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Table */}
              <div className="table-wrapper" style={{ border: "none" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Timestamp (UTC)</th>
                      <th>Organization / Tenant</th>
                      <th>Tracking Identifier</th>
                      <th>Mode</th>
                      <th>Carrier</th>
                      <th>Provider</th>
                      <th>Status</th>
                      <th>Credits</th>
                      <th>Request IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usageRecordsLoading ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: "center", padding: "3rem" }}>
                          <span className="spinner" style={{ width: "2rem", height: "2rem", color: "var(--accent-blue)" }} />
                          <div style={{ marginTop: "0.5rem", fontSize: "0.85rem", color: "var(--text-muted)" }}>Loading records...</div>
                        </td>
                      </tr>
                    ) : usageRecords.length === 0 ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: "center", padding: "2.5rem", color: "var(--text-muted)" }}>
                          No usage records found matching the filter criteria.
                        </td>
                      </tr>
                    ) : (
                      usageRecords.map((r) => {
                        const statusUpper = (r.status || "").toUpperCase();
                        const isDelivered = statusUpper.includes("DELIVERED") || statusUpper.includes("RETURNED");
                        const isInTransit = statusUpper.includes("TRANSIT") || statusUpper.includes("DEPARTED") || statusUpper.includes("DISCHARGED") || statusUpper.includes("LOADED");
                        return (
                          <tr key={r.id}>
                            <td style={{ fontSize: "0.82rem", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                              {r.created_at ? new Date(r.created_at).toLocaleString() : "--"}
                            </td>
                            <td>
                              <div style={{ fontWeight: "600", fontSize: "0.85rem", color: "#0f172a" }}>
                                {r.tenant_name || `Tenant #${r.tenant_id}`}
                              </div>
                              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                                {r.tenant_slug}
                              </span>
                            </td>
                            <td>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                                <span style={{ fontFamily: "var(--font-mono)", fontWeight: "700" }}>{r.tracking_number}</span>
                                <button
                                  onClick={() => {
                                    navigator.clipboard.writeText(r.tracking_number);
                                    alert(`Copied "${r.tracking_number}" to clipboard`);
                                  }}
                                  style={{ background: "none", border: "none", cursor: "pointer", fontSize: "0.8rem", opacity: 0.6 }}
                                  title="Copy tracking number"
                                >
                                  📋
                                </button>
                              </div>
                            </td>
                            <td>
                              <span className={`badge badge-${(r.transport_mode || "SEA").toLowerCase()}`}>
                                {r.transport_mode === "AIR" ? "✈️ AIR" : "🚢 SEA"}
                              </span>
                            </td>
                            <td>
                              <div style={{ fontWeight: "600", fontSize: "0.85rem" }}>
                                {r.carrier_name || r.carrier_code || "--"}
                              </div>
                              {r.carrier_code && r.carrier_code !== r.carrier_name && (
                                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                                  Code: {r.carrier_code}
                                </span>
                              )}
                            </td>
                            <td>
                              <code style={{ fontSize: "0.78rem", background: "#f1f5f9", padding: "2px 6px", borderRadius: "4px" }}>
                                {r.provider_used || "live_api"}
                              </code>
                            </td>
                            <td>
                              <span className={`badge ${isDelivered ? "badge-success" : isInTransit ? "badge-info" : "badge-warning"}`} style={{ fontSize: "0.75rem" }}>
                                {r.status || "IN TRANSIT"}
                              </span>
                            </td>
                            <td>
                              <span style={{ fontWeight: "700", color: "var(--text-main)", fontSize: "0.85rem" }}>
                                {r.credits_consumed || 1} cr
                              </span>
                            </td>
                            <td style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                              {r.request_ip || "Direct"}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 2: CARRIER HEALTH SLA */}
          {activeTab === "carriers" && (
            <div className="card" style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border-subtle)" }}>
                <h3 style={{ fontSize: "1.1rem", fontWeight: "700" }}>Carrier Network Connectivity SLA</h3>
                <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  Real-time health telemetry across all 20+ Air Cargo carriers and Ocean Shipping Lines.
                </p>
              </div>

              <div className="table-wrapper" style={{ border: "none" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Carrier Code</th>
                      <th>Carrier Name</th>
                      <th>Transport Mode</th>
                      <th>Operational Status</th>
                      <th>Success SLA</th>
                      <th>Average Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {carriers.map((c) => (
                      <tr key={c.code}>
                        <td style={{ fontFamily: "var(--font-mono)", fontWeight: "700" }}>{c.code}</td>
                        <td style={{ fontWeight: "600" }}>{c.name}</td>
                        <td><span className={`badge badge-${c.mode.toLowerCase()}`}>{c.mode}</span></td>
                        <td>
                          <span className={`badge ${c.status === "HEALTHY" ? "badge-success" : (c.status === "DEGRADED" ? "badge-warning" : "badge-danger")}`}>
                            ● {c.status}
                          </span>
                        </td>
                        <td style={{ fontWeight: "700", color: c.success_rate_percent >= 95 ? "var(--accent-emerald)" : "var(--accent-amber)" }}>
                          {c.success_rate_percent}%
                        </td>
                        <td style={{ fontFamily: "var(--font-mono)" }}>{c.average_latency_ms} ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: PROVIDER TELEMETRY LOGS & CURL DEBUGGER */}
          {activeTab === "telemetry" && (
            <div className="card" style={{ padding: 0, overflow: "hidden" }}>
              <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border-subtle)" }}>
                <h3 style={{ fontSize: "1.1rem", fontWeight: "700" }}>Real-Time Provider Execution Logs</h3>
                <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                  Inspect every external carrier HTTP request, fallback invocation, response code, and copyable cURL command.
                </p>
              </div>

              <div className="table-wrapper" style={{ border: "none" }}>
                <table>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Tracking Number</th>
                      <th>Provider Invoked</th>
                      <th>Status</th>
                      <th>HTTP Code</th>
                      <th>Latency</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((l) => (
                      <tr key={l.id}>
                        <td style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                          {l.created_at ? new Date(l.created_at).toLocaleTimeString() : "--"}
                        </td>
                        <td style={{ fontFamily: "var(--font-mono)", fontWeight: "700" }}>{l.tracking_number}</td>
                        <td><code>{l.provider_name}</code></td>
                        <td>
                          <span className={`badge ${l.status === "SUCCESS" ? "badge-success" : (l.status === "FALLBACK" ? "badge-warning" : "badge-danger")}`}>
                            {l.status}
                          </span>
                        </td>
                        <td><strong>{l.http_status_code || "--"}</strong></td>
                        <td>{l.latency_ms ? `${Math.round(l.latency_ms)}ms` : "--"}</td>
                        <td>
                          {l.request_curl && (
                            <button
                              onClick={() => { setSelectedLog(l); setCurlModalOpen(true); }}
                              className="btn btn-secondary btn-sm"
                            >
                              Inspect cURL 🔍
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* MODAL 1: ONBOARD NEW TENANT */}
      {onboardModalOpen && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: "560px" }}>
            <div className="modal-header">
              <h3 className="modal-title"><span>🏢</span> Superadmin: Onboard Enterprise Tenant</h3>
              <button className="modal-close" onClick={() => setOnboardModalOpen(false)}>&times;</button>
            </div>

            {!onboardSuccessData ? (
              <form onSubmit={handleOnboardTenant}>
                {onboardError && (
                  <div style={{ padding: "0.75rem", background: "#fef2f2", color: "#b91c1c", borderRadius: "6px", fontSize: "0.85rem", marginBottom: "1rem" }}>
                    {onboardError}
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Organization Legal Name</label>
                  <input
                    type="text"
                    className="form-input"
                    required
                    placeholder="e.g. Apex Global Logistics"
                    value={newOrgName}
                    onChange={(e) => {
                      setNewOrgName(e.target.value);
                      if (!newSlug) setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
                    }}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Tenant Slug (Unique URL Identifier)</label>
                  <input
                    type="text"
                    className="form-input"
                    required
                    placeholder="e.g. apex-global"
                    value={newSlug}
                    onChange={(e) => setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                  />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <div className="form-group">
                    <label className="form-label">Subscription Tier</label>
                    <select className="form-select" value={newTier} onChange={(e) => setNewTier(e.target.value)}>
                      <option value="developer">Developer (100 tracks)</option>
                      <option value="growth">Growth ($199 - 2.5k tracks)</option>
                      <option value="business">Business ($699 - 15k tracks)</option>
                      <option value="enterprise">Enterprise ($2,499 - 1M tracks)</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label className="form-label">Monthly Quota Override (Optional)</label>
                    <input
                      type="number"
                      className="form-input"
                      placeholder="Default for tier"
                      value={newQuota}
                      onChange={(e) => setNewQuota(e.target.value)}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Root Admin User Email</label>
                  <input
                    type="email"
                    className="form-input"
                    required
                    placeholder="ops@apexlogistics.com"
                    value={newAdminEmail}
                    onChange={(e) => setNewAdminEmail(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Initial Root Admin Password</label>
                  <input
                    type="text"
                    className="form-input"
                    required
                    placeholder="Admin@2026!Cargo"
                    value={newAdminPassword}
                    onChange={(e) => setNewAdminPassword(e.target.value)}
                  />
                </div>

                <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
                  <input
                    type="checkbox"
                    id="overageCheck"
                    checked={newAllowOverage}
                    onChange={(e) => setNewAllowOverage(e.target.checked)}
                  />
                  <label htmlFor="overageCheck" style={{ fontSize: "0.85rem", color: "var(--text-secondary)", cursor: "pointer" }}>
                    Allow overage usage billing beyond monthly credit limit
                  </label>
                </div>

                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setOnboardModalOpen(false)}>Cancel</button>
                  <button type="submit" disabled={onboardLoading} className="btn btn-primary">
                    {onboardLoading ? "Provisioning..." : "Onboard Organization"}
                  </button>
                </div>
              </form>
            ) : (
              <div style={{ textAlign: "center", padding: "1rem 0" }}>
                <div style={{ fontSize: "2.5rem", marginBottom: "0.5rem" }}>🎉</div>
                <h4 style={{ fontSize: "1.25rem", fontWeight: "800", color: "var(--text-main)", marginBottom: "0.5rem" }}>
                  Tenant Organization Provisioned!
                </h4>
                <p style={{ fontSize: "0.88rem", color: "var(--text-muted)", marginBottom: "1rem" }}>
                  Organization <strong>{onboardSuccessData.tenant?.name}</strong> has been created with initial admin <strong>{onboardSuccessData.admin_user?.email}</strong>.
                </p>

                <div style={{ textAlign: "left", marginBottom: "0.5rem", fontSize: "0.82rem", fontWeight: "700", color: "var(--text-secondary)" }}>
                  Initial Production API Key Secret:
                </div>

                <div className="secret-reveal-card">
                  <span>{onboardSuccessData.api_key?.secret_key || onboardSuccessData.api_key?.key}</span>
                  <button
                    onClick={() => {
                      const secret = onboardSuccessData.api_key?.secret_key || onboardSuccessData.api_key?.key;
                      if (secret) navigator.clipboard.writeText(secret);
                      alert("API key copied to clipboard!");
                    }}
                    className="btn btn-secondary btn-sm"
                  >
                    Copy
                  </button>
                </div>

                <div style={{ marginTop: "1.5rem", display: "flex", justifyContent: "center", gap: "0.75rem" }}>
                  <button onClick={() => { setOnboardModalOpen(false); setOnboardSuccessData(null); }} className="btn btn-primary">
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* MODAL 2: QUOTA ADJUSTER */}
      {quotaModalOpen && selectedTenant && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: "480px" }}>
            <div className="modal-header">
              <h3 className="modal-title"><span>⚡</span> Adjust Quota: {selectedTenant.name}</h3>
              <button className="modal-close" onClick={() => setQuotaModalOpen(false)}>&times;</button>
            </div>

            <form onSubmit={handleUpdateQuota}>
              <div style={{ background: "var(--bg-secondary)", padding: "1rem", borderRadius: "6px", marginBottom: "1.25rem", fontSize: "0.85rem" }}>
                <div>Current Monthly Quota: <strong>{selectedTenant.monthly_quota} credits</strong></div>
                <div>Current Usage This Month: <strong>{selectedTenant.current_usage} requests</strong></div>
              </div>

              <div className="form-group">
                <label className="form-label">Add Bonus Credits (Top-Up)</label>
                <input
                  type="number"
                  className="form-input"
                  placeholder="e.g. 5000"
                  value={bonusCredits}
                  onChange={(e) => setBonusCredits(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  id="resetCheck"
                  checked={resetUsage}
                  onChange={(e) => setResetUsage(e.target.checked)}
                />
                <label htmlFor="resetCheck" style={{ fontSize: "0.85rem", cursor: "pointer" }}>
                  Reset current monthly usage to 0 credits
                </label>
              </div>

              <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  id="activeCheck"
                  checked={tenantStatusActive}
                  onChange={(e) => setTenantStatusActive(e.target.checked)}
                />
                <label htmlFor="activeCheck" style={{ fontSize: "0.85rem", cursor: "pointer" }}>
                  Tenant Account Status is <strong>Active</strong> (uncheck to suspend account)
                </label>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setQuotaModalOpen(false)}>Cancel</button>
                <button type="submit" disabled={quotaLoading} className="btn btn-primary">
                  {quotaLoading ? "Saving..." : "Apply Adjustments"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 3: CURL INSPECTOR */}
      {curlModalOpen && selectedLog && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: "700px" }}>
            <div className="modal-header">
              <h3 className="modal-title"><span>🔍</span> Telemetry Inspector: {selectedLog.tracking_number}</h3>
              <button className="modal-close" onClick={() => setCurlModalOpen(false)}>&times;</button>
            </div>

            <div style={{ marginBottom: "1rem", display: "flex", gap: "1rem", fontSize: "0.85rem" }}>
              <span>Provider: <code>{selectedLog.provider_name}</code></span>
              <span>HTTP Status: <strong>{selectedLog.http_status_code}</strong></span>
              <span>Latency: <strong>{Math.round(selectedLog.latency_ms || 0)}ms</strong></span>
            </div>

            <div style={{ background: "#0f172a", color: "#f8fafc", padding: "1.25rem", borderRadius: "8px", fontFamily: "var(--font-mono)", fontSize: "0.82rem", overflowX: "auto", maxHeight: "300px" }}>
              <pre style={{ margin: 0 }}><code>{selectedLog.request_curl}</code></pre>
            </div>

            <div className="modal-footer">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(selectedLog.request_curl);
                  alert("cURL command copied!");
                }}
                className="btn btn-primary"
              >
                Copy cURL Command
              </button>
              <button onClick={() => setCurlModalOpen(false)} className="btn btn-secondary">
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
