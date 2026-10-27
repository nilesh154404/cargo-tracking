"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  loginUser,
  getTenantProfile,
  getTenantUsage,
  trackShipment,
  batchTrackShipments,
  listApiKeys,
  createApiKey,
  revokeApiKey,
  getSubscriptionPlans,
  upgradeSubscriptionPlan,
  getShipmentHistory,
  STORAGE_KEYS
} from "@/lib/api";

export default function TenantPortalPage() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [user, setUser] = useState(null);
  const [tenant, setTenant] = useState(null);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Portal Login State
  const [loginEmail, setLoginEmail] = useState("admin@demologistics.com");
  const [loginPassword, setLoginPassword] = useState("demo123");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // Single Track State - 7 Parameters
  const [trackQuery, setTrackQuery] = useState("");
  const [mawbOblNo, setMawbOblNo] = useState("");
  const [containerNo, setContainerNo] = useState("");
  const [carrierCode, setCarrierCode] = useState("");
  const [carrierName, setCarrierName] = useState("");
  const [vesselName, setVesselName] = useState("");
  const [hawbHblNo, setHawbHblNo] = useState("");
  const [flightNo, setFlightNo] = useState("");
  const [showAdvancedParams, setShowAdvancedParams] = useState(false);
  const [selectedContainerFilter, setSelectedContainerFilter] = useState("ALL");
  const [trackLoading, setTrackLoading] = useState(false);
  const [singleResult, setSingleResult] = useState(null);
  const [trackError, setTrackError] = useState("");

  // Batch Track State
  const [batchInput, setBatchInput] = useState("MSMU6484830\nMEDU9650838\n160-15246221");
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchResults, setBatchResults] = useState(null);

  // API Keys State
  const [apiKeys, setApiKeys] = useState([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [newCreatedSecret, setNewCreatedSecret] = useState(null);
  const [keyModalOpen, setKeyModalOpen] = useState(false);

  // Subscription Plans
  const [plans, setPlans] = useState([]);
  const [upgradeLoading, setUpgradeLoading] = useState(false);

  // Recent Shipments
  const [recentShipments, setRecentShipments] = useState([]);

  useEffect(() => {
    loadPortalData();
  }, []);

  const loadPortalData = async () => {
    setLoading(true);
    try {
      const token = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEYS.TOKEN) : null;
      if (!token) {
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }

      const me = await getTenantProfile();
      if (!me) {
        throw new Error("Invalid tenant profile response");
      }
      setUser(me.user);
      setTenant(me.tenant || {
        name: "Platform Superadmin Workspace",
        slug: "superadmin",
        tier: "enterprise",
        monthly_quota: 1000000,
        current_usage: 0,
        remaining_credits: 1000000,
      });
      setIsAuthenticated(true);

      const usageData = await getTenantUsage().catch(() => null);
      setUsage(usageData);

      const keysData = await listApiKeys().catch(() => []);
      setApiKeys(keysData);

      const plansData = await getSubscriptionPlans().catch(() => []);
      setPlans(plansData);

      const shipmentsData = await getShipmentHistory(10).catch(() => []);
      setRecentShipments(shipmentsData);
    } catch (err) {
      console.warn("Portal load session expired or unauthenticated:", err);
      if (typeof window !== "undefined") {
        localStorage.removeItem(STORAGE_KEYS.TOKEN);
        localStorage.removeItem(STORAGE_KEYS.USER);
        localStorage.removeItem(STORAGE_KEYS.TENANT);
      }
      setIsAuthenticated(false);
    } finally {
      setLoading(false);
    }
  };

  const handlePortalLogin = async (e) => {
    if (e) e.preventDefault();
    setLoginLoading(true);
    setLoginError("");
    try {
      const data = await loginUser(loginEmail.trim(), loginPassword);
      setUser(data.user);
      setTenant(data.tenant);
      setIsAuthenticated(true);
      await loadPortalData();
    } catch (err) {
      setLoginError(err.message || "Invalid email or password.");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleSingleTrack = async (e, customOverrides = null) => {
    if (e) e.preventDefault();
    const mawb = (customOverrides?.MAWB_OBL_NO !== undefined ? customOverrides.MAWB_OBL_NO : mawbOblNo).trim();
    const cntr = (customOverrides?.CONTAINER_NO !== undefined ? customOverrides.CONTAINER_NO : containerNo).trim();
    const legacyQ = (customOverrides?.query !== undefined ? customOverrides.query : trackQuery).trim();

    if (!mawb && !cntr && !legacyQ) {
      setTrackError("Either MAWB / OBL / Booking No or Container No is required.");
      return;
    }

    setTrackLoading(true);
    setTrackError("");
    setSingleResult(null);
    setSelectedContainerFilter("ALL");

    try {
      const payload = {
        MAWB_OBL_NO: mawb || undefined,
        CONTAINER_NO: cntr || undefined,
        CARRIER_CODE: (customOverrides?.CARRIER_CODE !== undefined ? customOverrides.CARRIER_CODE : carrierCode).trim() || undefined,
        CARRIER_NAME: (customOverrides?.CARRIER_NAME !== undefined ? customOverrides.CARRIER_NAME : carrierName).trim() || undefined,
        VESSEL_NAME: (customOverrides?.VESSEL_NAME !== undefined ? customOverrides.VESSEL_NAME : vesselName).trim() || undefined,
        HAWB_HBL_NO: (customOverrides?.HAWB_HBL_NO !== undefined ? customOverrides.HAWB_HBL_NO : hawbHblNo).trim() || undefined,
        FLIGHT_NO: (customOverrides?.FLIGHT_NO !== undefined ? customOverrides.FLIGHT_NO : flightNo).trim() || undefined,
        query: cntr || mawb || legacyQ,
      };
      const res = await trackShipment(payload);
      setSingleResult(res);
      // Refresh quota
      const u = await getTenantUsage().catch(() => null);
      if (u) setUsage(u);
    } catch (err) {
      setTrackError(err.message || "Failed to track shipment.");
    } finally {
      setTrackLoading(false);
    }
  };

  const handleBatchTrack = async () => {
    const lines = batchInput.split("\n").map(l => l.trim()).filter(Boolean);
    if (lines.length === 0) {
      alert("Please enter at least one tracking number.");
      return;
    }

    setBatchLoading(true);
    setBatchResults(null);

    try {
      const items = lines.map(line => {
        const parts = line.split(",").map(p => p.trim());
        return {
          query: parts[0],
          tracking_number: parts[0],
          carrier_code: parts[1] || null,
          customer_reference: parts[2] || null
        };
      });

      const res = await batchTrackShipments(items);
      setBatchResults(res);
      // Refresh usage
      const u = await getTenantUsage();
      setUsage(u);
    } catch (err) {
      alert(err.message || "Batch tracking failed.");
    } finally {
      setBatchLoading(false);
    }
  };

  const handleCreateKey = async (e) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;

    try {
      const res = await createApiKey(newKeyName.trim());
      const secret = res.secret_key || res.key;
      setNewCreatedSecret(secret);
      setNewKeyName("");
      const keys = await listApiKeys();
      setApiKeys(keys);
    } catch (err) {
      alert(err.message || "Failed to create API Key.");
    }
  };

  const handleRevokeKey = async (keyId) => {
    if (!confirm("Are you sure you want to revoke this API key? This action is permanent.")) return;
    try {
      await revokeApiKey(keyId);
      const keys = await listApiKeys();
      setApiKeys(keys);
    } catch (err) {
      alert(err.message || "Failed to revoke key.");
    }
  };

  const handleUpgradeTier = async (tierCode) => {
    if (!confirm(`Upgrade organization plan to '${tierCode.toUpperCase()}'?`)) return;
    setUpgradeLoading(true);
    try {
      await upgradeSubscriptionPlan(tierCode);
      alert(`Organization successfully upgraded to ${tierCode.toUpperCase()}!`);
      loadPortalData();
    } catch (err) {
      alert(err.message || "Failed to upgrade plan.");
    } finally {
      setUpgradeLoading(false);
    }
  };

  const handleSignOut = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEYS.TOKEN);
      localStorage.removeItem(STORAGE_KEYS.USER);
      localStorage.removeItem(STORAGE_KEYS.TENANT);
      window.location.href = "/";
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "var(--bg-primary)" }}>
        <div style={{ textAlign: "center" }}>
          <span className="spinner" style={{ width: "2.5rem", height: "2.5rem", color: "var(--accent-blue)" }} />
          <p style={{ marginTop: "1rem", color: "var(--text-secondary)", fontWeight: "600" }}>Loading Tenant Workspace...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f8fafc", padding: "1.5rem" }}>
        <div className="card" style={{ maxWidth: "460px", width: "100%", padding: "2.5rem", boxShadow: "var(--shadow-xl)" }}>
          <div style={{ textAlign: "center", marginBottom: "2rem" }}>
            <Link href="/" style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", fontSize: "1.4rem", fontWeight: "800", color: "#0f172a", textDecoration: "none", marginBottom: "0.75rem" }}>
              <span>⚡</span>
              <span>CargoTrk<span style={{ color: "var(--accent-cyan)" }}>.io</span></span>
            </Link>
            <h1 style={{ fontSize: "1.35rem", fontWeight: "800", color: "#0f172a" }}>Customer Workspace Sign In</h1>
            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
              Access your tenant dashboard, live tracking telemetry, and production API keys.
            </p>
          </div>

          <form onSubmit={handlePortalLogin}>
            {loginError && (
              <div style={{ padding: "0.75rem", background: "#fef2f2", color: "#b91c1c", borderRadius: "6px", fontSize: "0.85rem", marginBottom: "1rem" }}>
                {loginError}
              </div>
            )}

            <div className="form-group">
              <label className="form-label">Account Email</label>
              <input
                type="email"
                className="form-input"
                required
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                placeholder="admin@demologistics.com"
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

            <button type="submit" disabled={loginLoading} className="btn btn-primary" style={{ width: "100%", height: "46px", marginTop: "1.25rem", marginBottom: "1rem" }}>
              {loginLoading ? <><span className="spinner" /> Authenticating...</> : "Sign In to Tenant Workspace"}
            </button>

            <div style={{ textAlign: "center" }}>
              <Link href="/" style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textDecoration: "none" }}>
                ← Return to Public Homepage
              </Link>
            </div>
          </form>
        </div>
      </div>
    );
  }

  const quota = usage?.monthly_quota || tenant?.monthly_quota || 2500;
  const used = usage?.current_usage || tenant?.current_usage || 0;
  const pct = Math.min(Math.round((used / quota) * 100), 100);

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-primary)" }}>
      {/* Left Navigation Sidebar */}
      <aside style={{ width: "260px", background: "#ffffff", borderRight: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "1.5rem", borderBottom: "1px solid var(--border-subtle)" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "1.2rem", fontWeight: "800", color: "#0f172a" }}>
            <span>⚡</span>
            <span>CargoTrk<span style={{ color: "var(--accent-cyan)" }}>.io</span></span>
          </Link>
          <div style={{ marginTop: "0.75rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Tenant: <strong>{tenant?.name || "My Organization"}</strong>
          </div>
        </div>

        <nav style={{ padding: "1rem", display: "flex", flexDirection: "column", gap: "0.35rem", flex: 1 }}>
          {[
            { id: "dashboard", label: "Overview Dashboard", icon: "📊" },
            { id: "tracker", label: "Live Cargo Tracker", icon: "🔍" },
            { id: "batch", label: "Batch CSV Tracking", icon: "📦" },
            { id: "apikeys", label: "Developer API Keys", icon: "🔑" },
            { id: "billing", label: "Subscription & Quota", icon: "💳" },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
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
                cursor: "pointer",
                transition: "all 0.15s ease"
              }}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div style={{ padding: "1.25rem", borderTop: "1px solid var(--border-subtle)" }}>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>
            Signed in as <strong>{user?.email}</strong>
          </div>
          <button onClick={handleSignOut} className="btn btn-secondary btn-sm" style={{ width: "100%" }}>
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        {/* Top Header Bar */}
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
              {activeTab === "dashboard" && "Workspace Dashboard"}
              {activeTab === "tracker" && "Live Cargo Inspector"}
              {activeTab === "batch" && "High-Volume Batch Ingestion"}
              {activeTab === "apikeys" && "Developer Center & API Keys"}
              {activeTab === "billing" && "Subscription & Quota Management"}
            </h2>
            <span className="badge badge-air">{(tenant?.tier_code || "DEVELOPER").toUpperCase()} TIER</span>
          </div>

          {/* Quota Progress Pill */}
          <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
            <div style={{ width: "240px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", fontWeight: "600", marginBottom: "0.25rem", color: "var(--text-secondary)" }}>
                <span>Monthly Quota</span>
                <span>{used} / {quota} ({pct}%)</span>
              </div>
              <div style={{ height: "6px", background: "var(--bg-secondary)", borderRadius: "3px", overflow: "hidden" }}>
                <div style={{
                  height: "100%",
                  width: `${pct}%`,
                  background: pct > 90 ? "var(--accent-rose)" : (pct > 75 ? "var(--accent-amber)" : "var(--accent-blue)"),
                  transition: "width 0.3s ease"
                }} />
              </div>
            </div>

            <button onClick={() => setActiveTab("billing")} className="btn btn-outline btn-sm">
              + Add Credits
            </button>
          </div>
        </header>

        {/* Tab View Contents */}
        <div style={{ padding: "2rem", flex: 1 }}>
          {/* TAB 1: OVERVIEW DASHBOARD */}
          {activeTab === "dashboard" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
              {/* Metric Cards */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1.5rem" }}>
                <div className="card">
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: "600" }}>Monthly Credits Remaining</div>
                  <div style={{ fontSize: "2rem", fontWeight: "800", color: "var(--accent-blue)", margin: "0.5rem 0" }}>
                    {Math.max(quota - used, 0)}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Quota: {quota} tracks / mo</div>
                </div>

                <div className="card">
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: "600" }}>Active Monitored Shipments</div>
                  <div style={{ fontSize: "2rem", fontWeight: "800", color: "var(--accent-emerald)", margin: "0.5rem 0" }}>
                    {recentShipments.length}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Automated tracking cache enabled</div>
                </div>

                <div className="card">
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: "600" }}>Active Production API Keys</div>
                  <div style={{ fontSize: "2rem", fontWeight: "800", color: "var(--text-main)", margin: "0.5rem 0" }}>
                    {apiKeys.filter(k => k.is_active).length}
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Across ERP &amp; TMS webhooks</div>
                </div>

                <div className="card">
                  <div style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontWeight: "600" }}>Carrier Fallback SLA</div>
                  <div style={{ fontSize: "2rem", fontWeight: "800", color: "var(--accent-cyan)", margin: "0.5rem 0" }}>
                    99.8%
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Sub-second unified responses</div>
                </div>
              </div>

              {/* Quick Track Launcher */}
              <div className="card" style={{ padding: "1.75rem", background: "#ffffff" }}>
                <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "0.5rem" }}>Instant Live Cargo Query</h3>
                <p style={{ fontSize: "0.88rem", color: "var(--text-muted)", marginBottom: "1rem" }}>
                  Query real-time milestones for any Air Cargo AWB or Sea Shipping Line container.
                </p>
                <div style={{ display: "flex", gap: "0.75rem", maxWidth: "600px" }}>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. MSMU6484830 or 160-15246221..."
                    value={trackQuery}
                    onChange={(e) => setTrackQuery(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter") { setActiveTab("tracker"); handleSingleTrack(); } }}
                  />
                  <button
                    onClick={() => { setActiveTab("tracker"); handleSingleTrack(); }}
                    className="btn btn-primary"
                  >
                    Track Now
                  </button>
                </div>
              </div>

              {/* Recent Shipments Feed */}
              <div className="card" style={{ padding: 0, overflow: "hidden" }}>
                <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 style={{ fontSize: "1rem", fontWeight: "700" }}>Recent Tracked Cargo</h3>
                  <button onClick={() => setActiveTab("tracker")} className="btn btn-outline btn-sm">
                    + Track New Shipment
                  </button>
                </div>

                <div className="table-wrapper" style={{ border: "none" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>Tracking Identifier</th>
                        <th>Transport Mode</th>
                        <th>Carrier</th>
                        <th>Latest Status</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentShipments.length === 0 ? (
                        <tr>
                          <td colSpan={5} style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                            No tracked shipments yet. Use the Live Cargo Tracker to track your first container or AWB.
                          </td>
                        </tr>
                      ) : (
                        recentShipments.map((s, idx) => (
                          <tr key={idx}>
                            <td style={{ fontFamily: "var(--font-mono)", fontWeight: "700" }}>{s.tracking_number}</td>
                            <td><span className={`badge badge-${(s.transport_mode || "SEA").toLowerCase()}`}>{s.transport_mode || "SEA"}</span></td>
                            <td>{s.carrier_name || s.carrier_code || "--"}</td>
                            <td>
                              <span className={`badge ${(s.status || "").toUpperCase() === "DELIVERED" ? "badge-success" : "badge-warning"}`}>
                                {s.status || "IN TRANSIT"}
                              </span>
                            </td>
                            <td>
                              <button
                                onClick={() => { setTrackQuery(s.tracking_number); setActiveTab("tracker"); handleSingleTrack(); }}
                                className="btn btn-secondary btn-sm"
                              >
                                View Details ➔
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: LIVE CARGO TRACKER */}
          {activeTab === "tracker" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem", maxWidth: "960px" }}>
              <div className="card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <h3 style={{ fontSize: "1.15rem", fontWeight: "700" }}>Live Cargo Telemetry Inspector</h3>
                  <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", background: "var(--bg-secondary)", padding: "0.2rem 0.6rem", borderRadius: "4px" }}>
                    7-Parameter Enterprise Engine
                  </span>
                </div>
                <p style={{ fontSize: "0.86rem", color: "var(--text-secondary)", marginBottom: "1.25rem" }}>
                  Query real-time milestones across air airlines and ocean shipping lines. <strong>MAWB_OBL_NO</strong> or <strong>CONTAINER_NO</strong> is required; other parameters are logged for TMS audit.
                </p>

                <form onSubmit={handleSingleTrack} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                  {/* Two Primary Required-One Inputs */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "700", marginBottom: "0.35rem", color: "var(--text-primary)" }}>
                        MAWB_OBL_NO (Air AWB / Ocean B/L / Booking No)
                      </label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="e.g. ONEYBLRG06172700, BLRG06172700, 160-15246221"
                        value={mawbOblNo}
                        onChange={(e) => setMawbOblNo(e.target.value)}
                        style={{ fontFamily: "var(--font-mono)", fontSize: "0.95rem" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.8rem", fontWeight: "700", marginBottom: "0.35rem", color: "var(--text-primary)" }}>
                        CONTAINER_NO (Ocean Container Number)
                      </label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="e.g. ONEU2157736, ONEU1728682, MSMU6484830"
                        value={containerNo}
                        onChange={(e) => setContainerNo(e.target.value)}
                        style={{ fontFamily: "var(--font-mono)", fontSize: "0.95rem" }}
                      />
                    </div>
                  </div>

                  {/* Toggle Optional / Audit Parameters */}
                  <div>
                    <button
                      type="button"
                      onClick={() => setShowAdvancedParams(!showAdvancedParams)}
                      style={{
                        background: "none",
                        border: "none",
                        color: "var(--brand-primary)",
                        fontSize: "0.82rem",
                        fontWeight: "600",
                        cursor: "pointer",
                        padding: 0,
                        display: "flex",
                        alignItems: "center",
                        gap: "0.35rem"
                      }}
                    >
                      {showAdvancedParams ? "▲ Hide Optional TMS Audit Parameters" : "▼ Additional Parameters (Carrier Code, Carrier Name, Vessel, HAWB/HBL, Flight No)"}
                    </button>

                    {showAdvancedParams && (
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "0.75rem", marginTop: "0.85rem", padding: "1rem", background: "var(--bg-secondary)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
                        <div>
                          <label style={{ display: "block", fontSize: "0.74rem", fontWeight: "700", marginBottom: "0.25rem" }}>CARRIER_CODE</label>
                          <input
                            type="text"
                            className="form-input"
                            placeholder="e.g. ONE, CX, MSK"
                            value={carrierCode}
                            onChange={(e) => setCarrierCode(e.target.value)}
                            style={{ fontSize: "0.85rem" }}
                          />
                        </div>
                        <div>
                          <label style={{ display: "block", fontSize: "0.74rem", fontWeight: "700", marginBottom: "0.25rem" }}>CARRIER_NAME</label>
                          <input
                            type="text"
                            className="form-input"
                            placeholder="e.g. Ocean Network Express"
                            value={carrierName}
                            onChange={(e) => setCarrierName(e.target.value)}
                            style={{ fontSize: "0.85rem" }}
                          />
                        </div>
                        <div>
                          <label style={{ display: "block", fontSize: "0.74rem", fontWeight: "700", marginBottom: "0.25rem" }}>VESSEL_NAME</label>
                          <input
                            type="text"
                            className="form-input"
                            placeholder="e.g. X-PRESS KARAKORAM"
                            value={vesselName}
                            onChange={(e) => setVesselName(e.target.value)}
                            style={{ fontSize: "0.85rem" }}
                          />
                        </div>
                        <div>
                          <label style={{ display: "block", fontSize: "0.74rem", fontWeight: "700", marginBottom: "0.25rem" }}>HAWB_HBL_NO</label>
                          <input
                            type="text"
                            className="form-input"
                            placeholder="House AWB / B/L No"
                            value={hawbHblNo}
                            onChange={(e) => setHawbHblNo(e.target.value)}
                            style={{ fontSize: "0.85rem" }}
                          />
                        </div>
                        <div>
                          <label style={{ display: "block", fontSize: "0.74rem", fontWeight: "700", marginBottom: "0.25rem" }}>FLIGHT_NO</label>
                          <input
                            type="text"
                            className="form-input"
                            placeholder="e.g. CX0802"
                            value={flightNo}
                            onChange={(e) => setFlightNo(e.target.value)}
                            style={{ fontSize: "0.85rem" }}
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Submit Button & Presets */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem", marginTop: "0.5rem" }}>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                      <span style={{ fontSize: "0.76rem", color: "var(--text-muted)", fontWeight: "600" }}>Live Demos:</span>
                      <button
                        type="button"
                        onClick={() => {
                          setMawbOblNo("ONEYBLRG06172700");
                          setContainerNo("");
                          setCarrierCode("ONE");
                          handleSingleTrack(null, { MAWB_OBL_NO: "ONEYBLRG06172700", CONTAINER_NO: "", CARRIER_CODE: "ONE" });
                        }}
                        className="btn btn-outline btn-sm"
                        style={{ fontSize: "0.74rem", padding: "0.2rem 0.5rem" }}
                      >
                        🚢 ONE Booking (5 Containers)
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setContainerNo("ONEU2157736");
                          setMawbOblNo("");
                          setCarrierCode("ONE");
                          handleSingleTrack(null, { CONTAINER_NO: "ONEU2157736", MAWB_OBL_NO: "", CARRIER_CODE: "ONE" });
                        }}
                        className="btn btn-outline btn-sm"
                        style={{ fontSize: "0.74rem", padding: "0.2rem 0.5rem" }}
                      >
                        🚢 ONE Container (ONEU2157736)
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setMawbOblNo("160-15246221");
                          setContainerNo("");
                          setCarrierCode("CX");
                          handleSingleTrack(null, { MAWB_OBL_NO: "160-15246221", CONTAINER_NO: "", CARRIER_CODE: "CX" });
                        }}
                        className="btn btn-outline btn-sm"
                        style={{ fontSize: "0.74rem", padding: "0.2rem 0.5rem" }}
                      >
                        ✈️ Cathay Air AWB (160-15246221)
                      </button>
                    </div>

                    <button type="submit" disabled={trackLoading} className="btn btn-primary" style={{ minWidth: "160px", height: "42px" }}>
                      {trackLoading ? <><span className="spinner" /> Querying Live Telemetry...</> : "Track Cargo Live"}
                    </button>
                  </div>
                </form>

                {trackError && (
                  <div style={{ marginTop: "1rem", padding: "0.75rem 1rem", background: "#fef2f2", color: "#b91c1c", borderRadius: "6px", fontSize: "0.88rem", border: "1px solid #fecaca" }}>
                    ⚠️ {trackError}
                  </div>
                )}
              </div>

              {/* Single Track Result */}
              {singleResult && (
                <div className="card">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "1rem", marginBottom: "1.5rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
                      <span className={`badge badge-${(singleResult.mode || "SEA").toLowerCase()}`}>{singleResult.mode || "SEA"}</span>
                      <span style={{ fontSize: "1.4rem", fontWeight: "800", fontFamily: "var(--font-mono)" }}>{singleResult.tracking_number}</span>
                      <span style={{ fontWeight: "600", color: "var(--text-secondary)" }}>{singleResult.carrier?.name || singleResult.carrier_code}</span>
                      {singleResult.vessel_name && (
                        <span style={{ fontSize: "0.82rem", background: "#f1f5f9", padding: "0.2rem 0.6rem", borderRadius: "4px", color: "#334155" }}>
                          🚢 Vessel: <strong>{singleResult.vessel_name}</strong>
                        </span>
                      )}
                    </div>
                    <span className={`badge ${(singleResult.status || "").toUpperCase().includes("DELIVER") || (singleResult.status || "").toUpperCase().includes("RETURN") ? "badge-success" : "badge-warning"}`}>
                      {singleResult.status}
                    </span>
                  </div>

                  {/* Multi-Container Management Panel if booking tracking returned multiple containers */}
                  {singleResult.containers && singleResult.containers.length > 0 && (
                    <div style={{ marginBottom: "1.75rem", padding: "1.25rem", background: "var(--bg-secondary)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                        <div>
                          <h4 style={{ fontSize: "0.98rem", fontWeight: "700", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            📦 Containers in Shipment ({singleResult.containers.length})
                          </h4>
                          <span style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                            Aggregated booking telemetry across all containers. Filter milestones below or view combined timeline.
                          </span>
                        </div>
                        {singleResult.weight && (
                          <div style={{ fontSize: "0.82rem", background: "#ffffff", padding: "0.3rem 0.75rem", borderRadius: "6px", border: "1px solid var(--border-subtle)", fontWeight: "600" }}>
                            ⚖️ Total Weight: {singleResult.weight.value?.toLocaleString()} {singleResult.weight.unit || "kg"}
                          </div>
                        )}
                      </div>

                      {/* Containers Grid Table */}
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.75rem", marginBottom: "1rem" }}>
                        {singleResult.containers.map((c, i) => (
                          <div
                            key={i}
                            onClick={() => setSelectedContainerFilter(selectedContainerFilter === c.container_number ? "ALL" : c.container_number)}
                            style={{
                              padding: "0.75rem 1rem",
                              background: selectedContainerFilter === c.container_number ? "#eff6ff" : "#ffffff",
                              borderRadius: "6px",
                              border: `1.5px solid ${selectedContainerFilter === c.container_number ? "var(--brand-primary)" : "var(--border-subtle)"}`,
                              cursor: "pointer",
                              transition: "all 0.15s ease",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontFamily: "var(--font-mono)", fontWeight: "800", fontSize: "0.92rem", color: "var(--brand-primary)" }}>
                                {c.container_number}
                              </span>
                              <span style={{ fontSize: "0.7rem", background: "var(--bg-secondary)", padding: "0.15rem 0.4rem", borderRadius: "3px" }}>
                                {c.container_type || "CNTR"}
                              </span>
                            </div>
                            <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)", marginTop: "0.3rem" }}>
                              {c.status || "In Transit"}
                            </div>
                            {c.weight && (
                              <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.15rem" }}>
                                {c.weight}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Filter Pills */}
                      <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap", alignItems: "center" }}>
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: "600" }}>Filter Timeline:</span>
                        <button
                          type="button"
                          onClick={() => setSelectedContainerFilter("ALL")}
                          className={`btn btn-sm ${selectedContainerFilter === "ALL" ? "btn-primary" : "btn-outline"}`}
                          style={{ fontSize: "0.74rem", padding: "0.2rem 0.55rem" }}
                        >
                          All Containers ({singleResult.events?.length || 0})
                        </button>
                        {singleResult.containers.map((c, idx) => {
                          const count = (singleResult.events || []).filter(ev =>
                            (ev.flight_info || "").includes(c.container_number) ||
                            (ev.status_message || "").includes(c.container_number)
                          ).length;
                          return (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => setSelectedContainerFilter(c.container_number)}
                              className={`btn btn-sm ${selectedContainerFilter === c.container_number ? "btn-primary" : "btn-outline"}`}
                              style={{ fontSize: "0.74rem", padding: "0.2rem 0.55rem", fontFamily: "var(--font-mono)" }}
                            >
                              {c.container_number} ({count})
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Route Origin & Destination with verified coordinates */}
                  {(singleResult.origin || singleResult.destination) && (
                    <div style={{ display: "flex", gap: "2rem", marginBottom: "1.5rem", padding: "0.85rem 1.25rem", background: "var(--bg-secondary)", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)", flexWrap: "wrap" }}>
                      {singleResult.origin && (
                        <div>
                          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>Origin Port</div>
                          <div style={{ fontWeight: "700", fontSize: "0.95rem", display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.15rem" }}>
                            {singleResult.mode === "AIR" ? "🛫" : "⚓"} {singleResult.origin}
                            {singleResult.origin_coordinates && (
                              <a
                                href={`https://www.google.com/maps?q=${singleResult.origin_coordinates.lat},${singleResult.origin_coordinates.lng}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  fontSize: "0.72rem",
                                  background: "#f0fdf4",
                                  color: "#166534",
                                  padding: "0.15rem 0.45rem",
                                  borderRadius: "4px",
                                  border: "1px solid #bbf7d0",
                                  textDecoration: "none",
                                  fontWeight: "600"
                                }}
                                title={`Open ${singleResult.origin_coordinates.matched_name || singleResult.origin} in Maps`}
                              >
                                📍 {singleResult.origin_coordinates.lat.toFixed(2)}°, {singleResult.origin_coordinates.lng.toFixed(2)}° ↗
                              </a>
                            )}
                          </div>
                        </div>
                      )}
                      {singleResult.destination && (
                        <div>
                          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>Destination Port</div>
                          <div style={{ fontWeight: "700", fontSize: "0.95rem", display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.15rem" }}>
                            {singleResult.mode === "AIR" ? "🛬" : "⚓"} {singleResult.destination}
                            {singleResult.destination_coordinates && (
                              <a
                                href={`https://www.google.com/maps?q=${singleResult.destination_coordinates.lat},${singleResult.destination_coordinates.lng}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  fontSize: "0.72rem",
                                  background: "#f0fdf4",
                                  color: "#166534",
                                  padding: "0.15rem 0.45rem",
                                  borderRadius: "4px",
                                  border: "1px solid #bbf7d0",
                                  textDecoration: "none",
                                  fontWeight: "600"
                                }}
                                title={`Open ${singleResult.destination_coordinates.matched_name || singleResult.destination} in Maps`}
                              >
                                📍 {singleResult.destination_coordinates.lat.toFixed(2)}°, {singleResult.destination_coordinates.lng.toFixed(2)}° ↗
                              </a>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  <h4 style={{ fontSize: "1rem", fontWeight: "700", marginBottom: "1rem" }}>
                    Chronological Milestone Telemetry (Descending)
                    {selectedContainerFilter !== "ALL" && (
                      <span style={{ fontSize: "0.82rem", fontWeight: "500", color: "var(--brand-primary)", marginLeft: "0.75rem" }}>
                        Filtered by container: <strong>{selectedContainerFilter}</strong>
                      </span>
                    )}
                  </h4>

                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    {[...(singleResult.events || [])]
                      .filter(ev => {
                        if (selectedContainerFilter === "ALL") return true;
                        return (
                          (ev.flight_info || "").includes(selectedContainerFilter) ||
                          (ev.status_message || "").includes(selectedContainerFilter)
                        );
                      })
                      .sort((a, b) => new Date(b.event_time || b.timestamp || 0) - new Date(a.event_time || a.timestamp || 0))
                      .map((ev, idx) => {
                        const isLatest = idx === 0;
                        const t = new Date(ev.event_time || ev.timestamp || Date.now());
                        const dateStr = !isNaN(t.getTime()) ? t.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "-";
                        const timeStr = !isNaN(t.getTime()) ? t.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }) : "-";

                        return (
                          <div
                            key={idx}
                            style={{
                              display: "flex",
                              gap: "1.5rem",
                              padding: "1rem",
                              borderRadius: "var(--radius-md)",
                              background: isLatest ? "#eff6ff" : "var(--bg-secondary)",
                              border: `1px solid ${isLatest ? "#bfdbfe" : "var(--border-subtle)"}`
                            }}
                          >
                            <div style={{ minWidth: "120px" }}>
                              <div style={{ fontWeight: "700", fontSize: "0.85rem" }}>{dateStr}</div>
                              <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{timeStr}</div>
                            </div>
                            <div style={{ flex: 1 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                                <span style={{ fontWeight: "700", fontSize: "0.95rem" }}>
                                  {ev.status_message || ev.status || ev.status_code || "Checkpoint"}
                                </span>
                                {isLatest && <span className="badge badge-success" style={{ fontSize: "0.62rem" }}>LATEST</span>}
                              </div>
                              <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", fontSize: "0.78rem", marginTop: "0.35rem" }}>
                                {ev.station && <span style={{ background: "#ffffff", padding: "0.2rem 0.5rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>📍 {ev.station}</span>}
                                {ev.coordinates && (
                                  <a
                                    href={`https://www.google.com/maps?q=${ev.coordinates.lat},${ev.coordinates.lng}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                      background: "#f0fdf4",
                                      color: "#166534",
                                      padding: "0.2rem 0.5rem",
                                      borderRadius: "4px",
                                      border: "1px solid #bbf7d0",
                                      textDecoration: "none",
                                      fontWeight: "600",
                                      display: "inline-flex",
                                      alignItems: "center",
                                      gap: "0.25rem"
                                    }}
                                    title={`Open ${ev.coordinates.matched_name || ev.station} in Google Maps`}
                                  >
                                    🌐 {ev.coordinates.lat.toFixed(4)}°, {ev.coordinates.lng.toFixed(4)}° ({ev.coordinates.matched_code || ev.coordinates.location_type}) ↗
                                  </a>
                                )}
                                {ev.flight_info && <span style={{ background: "#ffffff", padding: "0.2rem 0.5rem", borderRadius: "4px", border: "1px solid var(--border-subtle)", fontFamily: "var(--font-mono)" }}>🚢/✈️ {ev.flight_info}</span>}
                                {ev.weight && <span style={{ background: "#ffffff", padding: "0.2rem 0.5rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>⚖️ {ev.weight}</span>}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: BATCH CSV TRACKING */}
          {activeTab === "batch" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem", maxWidth: "900px" }}>
              <div className="card">
                <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "0.5rem" }}>High-Volume Batch Tracking Ingestion</h3>
                <p style={{ fontSize: "0.88rem", color: "var(--text-muted)", marginBottom: "1.25rem" }}>
                  Paste up to 100 tracking identifiers (one per line, format: <code>TrackingNumber, CarrierCode, CustomerReference</code>) to execute concurrent tracking.
                </p>

                <textarea
                  className="form-textarea"
                  rows={6}
                  style={{ fontFamily: "var(--font-mono)", fontSize: "0.88rem", marginBottom: "1rem" }}
                  value={batchInput}
                  onChange={(e) => setBatchInput(e.target.value)}
                />

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <button
                    onClick={handleBatchTrack}
                    disabled={batchLoading}
                    className="btn btn-primary"
                  >
                    {batchLoading ? <><span className="spinner" /> Executing Batch...</> : "Run Batch Ingestion"}
                  </button>

                  <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                    Deducts 1 credit per processed shipment.
                  </span>
                </div>
              </div>

              {batchResults && (
                <div className="card" style={{ padding: 0, overflow: "hidden" }}>
                  <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <h4 style={{ fontWeight: "700" }}>
                      Batch Results ({batchResults.total_processed} processed, {batchResults.credits_consumed} credits consumed)
                    </h4>
                    <button
                      onClick={() => {
                        const csvContent = "data:text/csv;charset=utf-8," +
                          ["TrackingNumber,Mode,Carrier,Status,LatestEvent"]
                            .concat((batchResults.results || []).map(r => `"${r.tracking_number}","${r.mode}","${r.carrier?.name || ''}","${r.status}","${r.events?.[0]?.status_message || ''}"`))
                            .join("\n");
                        const encodedUri = encodeURI(csvContent);
                        const link = document.createElement("a");
                        link.setAttribute("href", encodedUri);
                        link.setAttribute("download", `batch_tracking_report_${Date.now()}.csv`);
                        document.body.appendChild(link);
                        link.click();
                      }}
                      className="btn btn-secondary btn-sm"
                    >
                      Export CSV Report
                    </button>
                  </div>

                  <div className="table-wrapper" style={{ border: "none" }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Tracking Number</th>
                          <th>Mode</th>
                          <th>Carrier</th>
                          <th>Status</th>
                          <th>Latest Checkpoint</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(batchResults.results || []).map((r, idx) => (
                          <tr key={idx}>
                            <td style={{ fontFamily: "var(--font-mono)", fontWeight: "700" }}>{r.tracking_number}</td>
                            <td><span className={`badge badge-${(r.mode || "SEA").toLowerCase()}`}>{r.mode}</span></td>
                            <td>{r.carrier?.name || "--"}</td>
                            <td>
                              <span className={`badge ${(r.status || "").toUpperCase() === "DELIVERED" ? "badge-success" : "badge-warning"}`}>
                                {r.status}
                              </span>
                            </td>
                            <td style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                              {r.events?.[0]?.status_message || "--"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: DEVELOPER API KEYS */}
          {activeTab === "apikeys" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem", maxWidth: "900px" }}>
              <div className="card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <div>
                    <h3 style={{ fontSize: "1.1rem", fontWeight: "700" }}>Active Production API Keys</h3>
                    <p style={{ fontSize: "0.88rem", color: "var(--text-muted)" }}>
                      Use these API keys to authenticate direct machine-to-machine REST requests via <code>X-API-Key</code>.
                    </p>
                  </div>
                  <button onClick={() => { setKeyModalOpen(true); setNewCreatedSecret(null); }} className="btn btn-primary btn-sm">
                    + Create New Key
                  </button>
                </div>

                <div className="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>Key Name</th>
                        <th>Prefix Identifier</th>
                        <th>Scopes</th>
                        <th>Status</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {apiKeys.length === 0 ? (
                        <tr>
                          <td colSpan={5} style={{ textAlign: "center", padding: "1.5rem", color: "var(--text-muted)" }}>
                            No API keys created yet. Click "+ Create New Key" to generate a production secret.
                          </td>
                        </tr>
                      ) : (
                        apiKeys.map((k) => (
                          <tr key={k.id}>
                            <td style={{ fontWeight: "600" }}>{k.name}</td>
                            <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.85rem" }}>{k.prefix || k.key_prefix}••••••••</td>
                            <td><span className="badge badge-tier" style={{ fontSize: "0.68rem" }}>{Array.isArray(k.scopes) ? k.scopes.join(", ") : (k.scopes || "tracking:live")}</span></td>
                            <td>
                              <span className={`badge ${k.is_active ? "badge-success" : "badge-danger"}`}>
                                {k.is_active ? "ACTIVE" : "REVOKED"}
                              </span>
                            </td>
                            <td>
                              {k.is_active && (
                                <button
                                  onClick={() => handleRevokeKey(k.id)}
                                  className="btn btn-secondary btn-sm"
                                  style={{ color: "var(--accent-rose)" }}
                                >
                                  Revoke
                                </button>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: SUBSCRIPTION & BILLING */}
          {activeTab === "billing" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
              <div className="card">
                <h3 style={{ fontSize: "1.1rem", fontWeight: "700", marginBottom: "0.5rem" }}>Current Subscription Tier</h3>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginTop: "1rem" }}>
                  <div style={{ fontSize: "1.75rem", fontWeight: "800", color: "var(--accent-blue)", textTransform: "capitalize" }}>
                    {tenant?.tier_code} Plan
                  </div>
                  <span className="badge badge-success">ACTIVE &amp; IN GOOD STANDING</span>
                </div>
                <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginTop: "0.5rem" }}>
                  Includes <strong>{tenant?.monthly_quota} tracks / month</strong> with <strong>{tenant?.rate_limit_rpm} Requests Per Minute</strong> rate limit.
                </p>
              </div>

              <div>
                <h3 style={{ fontSize: "1.25rem", fontWeight: "800", marginBottom: "1rem" }}>Upgrade Subscription Quota</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1.5rem" }}>
                  {plans.map((p) => {
                    const isCurrent = p.code === tenant?.tier_code;
                    return (
                      <div
                        key={p.code}
                        className="card"
                        style={{
                          border: isCurrent ? "2px solid var(--accent-blue)" : "1px solid var(--border-subtle)",
                          padding: "1.5rem",
                          display: "flex",
                          flexDirection: "column"
                        }}
                      >
                        <h4 style={{ fontSize: "1.2rem", fontWeight: "800", marginBottom: "0.25rem" }}>{p.name}</h4>
                        <div style={{ fontSize: "1.75rem", fontWeight: "800", margin: "0.75rem 0" }}>
                          ${p.price_usd_monthly}<span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>/mo</span>
                        </div>
                        <ul style={{ listStyle: "none", padding: 0, margin: "0 0 1.5rem", fontSize: "0.85rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.4rem", flex: 1 }}>
                          <li>✓ <strong>{p.monthly_credits.toLocaleString()}</strong> tracks / mo</li>
                          <li>✓ <strong>{p.rate_limit_rpm}</strong> RPM rate limit</li>
                          <li>✓ <strong>{p.max_api_keys}</strong> API keys</li>
                          {p.allow_batch && <li>✓ Batch CSV tracking</li>}
                        </ul>
                        <button
                          disabled={isCurrent || upgradeLoading}
                          onClick={() => handleUpgradeTier(p.code)}
                          className={`btn ${isCurrent ? "btn-secondary" : "btn-primary"}`}
                        >
                          {isCurrent ? "Active Plan" : `Upgrade to ${p.name}`}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Create API Key Modal */}
      {keyModalOpen && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3 className="modal-title"><span>🔑</span> Create Production API Key</h3>
              <button className="modal-close" onClick={() => setKeyModalOpen(false)}>&times;</button>
            </div>

            {!newCreatedSecret ? (
              <form onSubmit={handleCreateKey}>
                <div className="form-group">
                  <label className="form-label">Key Name / Description</label>
                  <input
                    type="text"
                    className="form-input"
                    required
                    placeholder="e.g. ERP Integration Key"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                  />
                </div>
                <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "1.5rem" }}>
                  This key will have full tracking scopes (<code>tracking:live</code>, <code>tracking:read</code>, <code>shipments:batch</code>).
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setKeyModalOpen(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary">Generate Secret Key</button>
                </div>
              </form>
            ) : (
              <div style={{ textAlign: "center", padding: "1rem 0" }}>
                <h4 style={{ fontSize: "1.1rem", fontWeight: "800", color: "var(--text-main)", marginBottom: "0.5rem" }}>API Key Generated</h4>
                <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: "1rem" }}>
                  Please copy this key now. For security reasons, you will not be able to view it again.
                </p>
                <div className="secret-reveal-card">
                  <span>{newCreatedSecret}</span>
                  <button onClick={() => { navigator.clipboard.writeText(newCreatedSecret); alert("API Key copied to clipboard!"); }} className="btn btn-secondary btn-sm">
                    Copy
                  </button>
                </div>
                <div style={{ marginTop: "1.5rem" }}>
                  <button onClick={() => { setKeyModalOpen(false); setNewCreatedSecret(null); }} className="btn btn-primary">
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
