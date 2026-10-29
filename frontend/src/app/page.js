"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { loginUser, registerOrganization, trackShipment, STORAGE_KEYS } from "@/lib/api";
import { CONTAINER_SAMPLES, getMockContainerTelemetry } from "@/lib/mockContainers";
import { useToast } from "@/components/Toast";

export default function MarketingHomePage() {
  const showToast = useToast();
  // Container Mock Tracking state
  const [trackingNumber, setTrackingNumber] = useState("MSMU6484830");
  const [containerTelemetry, setContainerTelemetry] = useState(() => getMockContainerTelemetry("MSMU6484830"));
  const [formatMode, setFormatMode] = useState("split"); // "split" | "standard" | "mobile" | "timeline"
  const [copiedFormat, setCopiedFormat] = useState(null);
  const [isTracking, setIsTracking] = useState(false);
  const [trackError, setTrackError] = useState("");

  // Auth & Session state
  const [currentUser, setCurrentUser] = useState(null);
  const [loginModalOpen, setLoginModalOpen] = useState(false);
  const [registerModalOpen, setRegisterModalOpen] = useState(false);
  const [authRequiredModalOpen, setAuthRequiredModalOpen] = useState(false);

  // Forms state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginAsStaff, setLoginAsStaff] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  const [regOrgName, setRegOrgName] = useState("");
  const [regSlug, setRegSlug] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regTier, setRegTier] = useState("growth");
  const [regLoading, setRegLoading] = useState(false);
  const [regError, setRegError] = useState("");
  const [newGeneratedKey, setNewGeneratedKey] = useState(null);

  // Active Code Tab
  const [activeCodeTab, setActiveCodeTab] = useState("curl");

  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(STORAGE_KEYS.USER);
      if (stored) {
        try { setCurrentUser(JSON.parse(stored)); } catch (e) {}
      }
    }
    // Preload default container telemetry so user sees live interactive response immediately
    const initial = getMockContainerTelemetry("MSMU6484830");
    setContainerTelemetry(initial);
  }, []);

  const handleTrackSubmit = async (numToTrack = trackingNumber) => {
    const num = String(numToTrack || "MSMU6484830").trim().toUpperCase();
    setTrackingNumber(num);
    setTrackError("");
    setIsTracking(true);

    try {
      // Use demo API key if user is not logged in
      const token = typeof window !== "undefined" ? localStorage.getItem("cargotrk_auth_token") : null;
      const apiKey = token ? null : "cargotrk_live_defaultdemo00000000000000000";
      const liveData = await trackShipment(num, apiKey);

      // Build the telemetry object the UI expects (standard + mobileApp)
      const mobileApp = {
        tracking_number: liveData.tracking_number,
        mode: liveData.mode,
        status: liveData.status,
        carrier_code: liveData.carrier?.code,
        carrier_name: liveData.carrier?.name,
        origin: liveData.origin,
        destination: liveData.destination,
        events: (liveData.events || []).map((ev) => ({
          status: ev.status_message || ev.status_code,
          location: ev.station,
          timestamp: ev.event_time,
          flight_info: ev.flight_info,
        })),
      };

      setContainerTelemetry({
        standard: liveData,
        mobileApp: mobileApp,
      });
    } catch (err) {
      console.warn("Live tracking failed, falling back to mock data:", err.message);
      setTrackError(err.message || "Tracking failed");
      // Fallback to mock data so the UI still renders something
      const telemetry = getMockContainerTelemetry(num);
      setContainerTelemetry(telemetry);
    } finally {
      setIsTracking(false);
    }
  };

  const copyToClipboard = (data, type) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(typeof data === "string" ? data : JSON.stringify(data, null, 2));
      setCopiedFormat(type);
      setTimeout(() => setCopiedFormat(null), 2500);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginLoading(true);
    setLoginError("");
    try {
      const data = await loginUser(loginEmail, loginPassword);
      setCurrentUser(data.user);
      setLoginModalOpen(false);
      if (loginAsStaff || data.user?.role === "SUPER_ADMIN") {
        localStorage.setItem(STORAGE_KEYS.STAFF_TOKEN, data.access_token);
        window.location.href = "/staff";
      } else {
        window.location.href = "/portal";
      }
    } catch (err) {
      setLoginError(err.message || "Invalid credentials.");
    } finally {
      setLoginLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setRegLoading(true);
    setRegError("");
    try {
      const data = await registerOrganization({
        name: regOrgName,
        slug: regSlug,
        email: regEmail,
        password: regPassword,
        tier_code: regTier,
      });
      const generatedKey = data.api_key?.secret_key || data.api_key?.key;
      setNewGeneratedKey(generatedKey);
      if (typeof window !== "undefined" && generatedKey) {
        setApiKey(generatedKey);
        localStorage.setItem(STORAGE_KEYS.USER_API_KEY, generatedKey);
      }
    } catch (err) {
      setRegError(err.message || "Registration failed.");
    } finally {
      setRegLoading(false);
    }
  };

  const handleSignOut = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEYS.TOKEN);
      localStorage.removeItem(STORAGE_KEYS.USER);
      localStorage.removeItem(STORAGE_KEYS.TENANT);
      localStorage.removeItem(STORAGE_KEYS.STAFF_TOKEN);
    }
    setCurrentUser(null);
  };

  // Helper for Journey Bar
  const getJourneyActiveIndex = (status) => {
    const s = (status || "").toUpperCase();
    if (s.includes("DELIVER")) return 5;
    if (s.includes("CUSTOMS") || s.includes("CLEAR")) return 4;
    if (s.includes("ARRIV") || s.includes("DISCHARGE")) return 3;
    if (s.includes("TRANSIT") || s.includes("DEPART") || s.includes("SAIL")) return 2;
    if (s.includes("GATE") || s.includes("LOAD")) return 1;
    return 0;
  };

  const journeySteps = ["BOOKED", "GATE_IN", "IN_TRANSIT", "PORT_ARRIVED", "CUSTOMS", "DELIVERED"];

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Top Sticky Header */}
      <header style={{
        background: "#ffffff",
        borderBottom: "1px solid var(--border-subtle)",
        position: "sticky",
        top: 0,
        zIndex: 50,
        boxShadow: "var(--shadow-sm)"
      }}>
        <div className="container" style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          height: "72px"
        }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: "0.6rem", fontSize: "1.3rem", fontWeight: "800", color: "#0f172a" }}>
            <span style={{ fontSize: "1.6rem" }}>⚡</span>
            <span>CargoTrk<span style={{ color: "var(--accent-cyan)" }}>.io</span></span>
          </Link>

          <nav className="landing-desktop-nav" style={{ display: "flex", alignItems: "center", gap: "1.75rem" }}>
            <a href="#tracker" style={{ fontSize: "0.9rem", fontWeight: "600", color: "var(--text-secondary)" }}>Live Tracker</a>
            <a href="#network" style={{ fontSize: "0.9rem", fontWeight: "600", color: "var(--text-secondary)" }}>Carriers</a>
            <a href="#code" style={{ fontSize: "0.9rem", fontWeight: "600", color: "var(--text-secondary)" }}>API Quickstart</a>
            <a href="#pricing" style={{ fontSize: "0.9rem", fontWeight: "600", color: "var(--text-secondary)" }}>Pricing</a>
          </nav>

          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            {currentUser ? (
              <>
                <Link href="/portal" className="btn btn-primary btn-sm">
                  Launch Portal ➔
                </Link>
                <button onClick={handleSignOut} className="btn btn-secondary btn-sm">
                  Sign Out
                </button>
              </>
            ) : (
              <>
                <button onClick={() => setLoginModalOpen(true)} className="btn btn-secondary btn-sm">
                  Sign In
                </button>
                <button onClick={() => setRegisterModalOpen(true)} className="btn btn-primary btn-sm">
                  Get API Key
                </button>
              </>
            )}
            <Link href="/staff" className="btn btn-outline btn-sm" style={{ borderStyle: "dashed" }}>
              Staff ➔
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section id="tracker" style={{ padding: "4rem 0 3rem", background: "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)" }}>
        <div className="container" style={{ textAlign: "center" }}>
          <div style={{ display: "inline-flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
            <span className="badge badge-air">AIR CARGO 20+</span>
            <span className="badge badge-sea">OCEAN CONTAINER</span>
            <span className="badge badge-success">METERED ENTERPRISE API</span>
          </div>

          <h1 style={{ fontSize: "3rem", fontWeight: "800", letterSpacing: "-0.03em", color: "#0f172a", maxWidth: "900px", margin: "0 auto 1.25rem", lineHeight: 1.15 }}>
            The Universal Cargo Intelligence &amp; <span className="gradient-text">Multi-Carrier Tracking</span> API
          </h1>

          <p style={{ fontSize: "1.15rem", color: "var(--text-secondary)", maxWidth: "720px", margin: "0 auto 2.5rem" }}>
            Connect to 20+ air cargo carriers and all major ocean shipping lines through one unified, metered API with automated fallback orchestration and sub-second responses.
          </p>

          {/* Interactive Ocean Container Tracking Sandbox */}
          <div className="card card-playground" style={{ maxWidth: "1050px", margin: "0 auto", boxShadow: "var(--shadow-xl)" }}>
            {/* Search Row */}
            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", marginBottom: "1.25rem" }}>
              <div style={{ flex: "1", minWidth: "280px", position: "relative" }}>
                <span style={{ position: "absolute", left: "1.25rem", top: "50%", transform: "translateY(-50%)", fontSize: "1.4rem" }}>🚢</span>
                <input
                  type="text"
                  className="form-input"
                  style={{
                    paddingLeft: "3.5rem",
                    height: "56px",
                    fontSize: "1.1rem",
                    fontWeight: "700",
                    fontFamily: "var(--font-mono)",
                    letterSpacing: "0.05em",
                    borderRadius: "var(--radius-md)"
                  }}
                  placeholder="Enter Container Number (e.g. MSMU6484830, ONEU2157736)..."
                  value={trackingNumber}
                  onChange={(e) => setTrackingNumber(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleTrackSubmit(); }}
                />
              </div>

              <button
                onClick={() => handleTrackSubmit()}
                className="btn btn-primary btn-lg"
                style={{ height: "56px", minWidth: "180px", fontSize: "1rem", fontWeight: "700" }}
              >
                {isTracking ? "⏳ Tracking..." : "Track Container ➔"}
              </button>
            </div>

            {/* Quick Ocean Container Samples */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.6rem", flexWrap: "wrap", fontSize: "0.85rem" }}>
              <span style={{ color: "var(--text-muted)", fontWeight: "700" }}>Container Samples:</span>
              {CONTAINER_SAMPLES.map((sample) => {
                const isSelected = trackingNumber === sample.container_no;
                return (
                  <button
                    key={sample.container_no}
                    type="button"
                    onClick={() => {
                      setTrackingNumber(sample.container_no);
                      handleTrackSubmit(sample.container_no);
                    }}
                    className={`btn btn-sm ${isSelected ? "btn-primary" : "btn-secondary"}`}
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.82rem",
                      borderColor: isSelected ? "var(--accent-blue)" : "var(--border-subtle)"
                    }}
                  >
                    🚢 {sample.carrier_code}: <strong>{sample.container_no}</strong>
                  </button>
                );
              })}
            </div>

            <div style={{ marginTop: "1rem", fontSize: "0.8rem", color: "var(--text-muted)", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem" }}>
              <span>⚡ <strong>Live Backend Tracking:</strong> Enter any AWB or Container number to track via real carrier APIs with automated fallback.</span>
            </div>
            {trackError && (
              <div style={{ marginTop: "0.75rem", padding: "0.6rem 1rem", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "var(--radius-md)", color: "#b91c1c", fontSize: "0.85rem", textAlign: "center" }}>
                ⚠️ {trackError} — Showing cached/mock data below.
              </div>
            )}

            {/* Dual Payload & Tracking Overview Display Box */}
            {containerTelemetry && (
              <div style={{ marginTop: "2rem", borderTop: "1px solid var(--border-subtle)", paddingTop: "2rem", textAlign: "left" }}>
                {/* Shipment Overview Header */}
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "1rem",
                  padding: "1.25rem 1.5rem",
                  background: "var(--bg-secondary)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
                    <span className="badge badge-sea">
                      SEA CONTAINER
                    </span>
                    <span style={{ fontSize: "1.45rem", fontWeight: "800", fontFamily: "var(--font-mono)", color: "var(--text-main)" }}>
                      {containerTelemetry.standard.tracking_number}
                    </span>
                    <span style={{ fontSize: "0.95rem", fontWeight: "600", color: "var(--text-secondary)" }}>
                      {containerTelemetry.standard.carrier?.name} ({containerTelemetry.standard.carrier?.code})
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span className={`badge ${containerTelemetry.standard.status === "DELIVERED" ? "badge-success" : containerTelemetry.standard.status === "GATE_IN" ? "badge-tier" : "badge-warning"}`}>
                      ● {containerTelemetry.standard.status.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>

                {/* Route & Vessel Meta Bar */}
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: "1rem",
                  margin: "1.25rem 0",
                  padding: "1rem 1.25rem",
                  background: "#ffffff",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "var(--radius-md)"
                }}>
                  <div>
                    <div style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: "700", color: "var(--text-muted)" }}>Origin Seaport</div>
                    <div style={{ fontSize: "0.9rem", fontWeight: "700", color: "var(--text-main)", marginTop: "0.2rem" }}>
                      {containerTelemetry.standard.origin}
                    </div>
                    {containerTelemetry.standard.origin_coordinates && (
                      <div style={{ fontSize: "0.75rem", color: "var(--accent-marine)", fontFamily: "var(--font-mono)" }}>
                        GPS: {containerTelemetry.standard.origin_coordinates.lat}, {containerTelemetry.standard.origin_coordinates.lng}
                      </div>
                    )}
                  </div>

                  <div>
                    <div style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: "700", color: "var(--text-muted)" }}>Destination Seaport</div>
                    <div style={{ fontSize: "0.9rem", fontWeight: "700", color: "var(--text-main)", marginTop: "0.2rem" }}>
                      {containerTelemetry.standard.destination}
                    </div>
                    {containerTelemetry.standard.destination_coordinates && (
                      <div style={{ fontSize: "0.75rem", color: "var(--accent-marine)", fontFamily: "var(--font-mono)" }}>
                        GPS: {containerTelemetry.standard.destination_coordinates.lat}, {containerTelemetry.standard.destination_coordinates.lng}
                      </div>
                    )}
                  </div>

                  <div>
                    <div style={{ fontSize: "0.75rem", textTransform: "uppercase", fontWeight: "700", color: "var(--text-muted)" }}>Vessel / Voyage</div>
                    <div style={{ fontSize: "0.9rem", fontWeight: "700", color: "var(--text-main)", marginTop: "0.2rem" }}>
                      {containerTelemetry.standard.vessel_name || "N/A"}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Gross: {containerTelemetry.standard.weight?.value?.toLocaleString()} {containerTelemetry.standard.weight?.unit} · Vol: {containerTelemetry.standard.volume} CBM
                    </div>
                  </div>
                </div>

                {/* Visual Milestone Journey Bar */}
                <div style={{ margin: "1.75rem 0", padding: "0 0.5rem", overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
                  <div style={{ position: "relative", display: "flex", justifyContent: "space-between", alignItems: "center", minWidth: "480px" }}>
                    {/* Background track line */}
                    <div style={{ position: "absolute", left: "20px", right: "20px", top: "18px", height: "4px", background: "var(--border-subtle)", zIndex: 1 }} />
                    {/* Active progress connector */}
                    <div style={{
                      position: "absolute",
                      left: "20px",
                      top: "18px",
                      height: "4px",
                      background: "var(--accent-blue)",
                      zIndex: 2,
                      width: `${(getJourneyActiveIndex(containerTelemetry.standard.status) / (journeySteps.length - 1)) * 100}%`,
                      transition: "width 0.4s ease"
                    }} />

                    {journeySteps.map((step, idx) => {
                      const activeIdx = getJourneyActiveIndex(containerTelemetry.standard.status);
                      const isCompleted = idx < activeIdx;
                      const isCurrent = idx === activeIdx;
                      return (
                        <div key={step} style={{ position: "relative", zIndex: 3, textAlign: "center" }}>
                          <div style={{
                            width: "36px",
                            height: "36px",
                            borderRadius: "50%",
                            background: isCompleted || isCurrent ? "var(--accent-blue)" : "#ffffff",
                            color: isCompleted || isCurrent ? "#ffffff" : "var(--text-muted)",
                            border: `2px solid ${isCompleted || isCurrent ? "var(--accent-blue)" : "var(--border-subtle)"}`,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontWeight: "700",
                            fontSize: "0.85rem",
                            margin: "0 auto 0.4rem"
                          }}>
                            {isCompleted ? "✓" : (idx + 1)}
                          </div>
                          <div style={{ fontSize: "0.72rem", fontWeight: "600", color: isCurrent ? "var(--accent-blue)" : "var(--text-secondary)", textTransform: "uppercase" }}>
                            {step.replace(/_/g, " ")}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Format Selector Bar */}
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flexWrap: "wrap",
                  gap: "0.75rem",
                  margin: "2rem 0 1rem",
                  padding: "0.75rem 1rem",
                  background: "var(--bg-secondary)",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                    <span style={{ fontSize: "0.85rem", fontWeight: "700", color: "var(--text-secondary)", marginRight: "0.25rem" }}>
                      Response Format:
                    </span>
                    <button
                      type="button"
                      onClick={() => setFormatMode("split")}
                      className={`btn btn-sm ${formatMode === "split" ? "btn-primary" : "btn-secondary"}`}
                    >
                      🔀 Split View (Both Formats)
                    </button>
                    <button
                      type="button"
                      onClick={() => setFormatMode("standard")}
                      className={`btn btn-sm ${formatMode === "standard" ? "btn-primary" : "btn-secondary"}`}
                    >
                      📋 Standard API Format
                    </button>
                    <button
                      type="button"
                      onClick={() => setFormatMode("mobile")}
                      className={`btn btn-sm ${formatMode === "mobile" ? "btn-primary" : "btn-secondary"}`}
                    >
                      📱 Mobile-App Format
                    </button>
                    <button
                      type="button"
                      onClick={() => setFormatMode("timeline")}
                      className={`btn btn-sm ${formatMode === "timeline" ? "btn-primary" : "btn-secondary"}`}
                    >
                      🕒 Timeline Events
                    </button>
                  </div>

                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(containerTelemetry.standard, "standard")}
                      className="btn btn-secondary btn-sm"
                    >
                      {copiedFormat === "standard" ? "✓ Copied Standard" : "Copy Standard JSON"}
                    </button>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(containerTelemetry.mobileApp, "mobile")}
                      className="btn btn-secondary btn-sm"
                    >
                      {copiedFormat === "mobile" ? "✓ Copied Mobile" : "Copy Mobile JSON"}
                    </button>
                  </div>
                </div>

                {/* TAB VIEWS */}
                {/* 1. SPLIT VIEW: Both Formats Side-by-Side */}
                {formatMode === "split" && (
                  <div className="grid-responsive-split">
                    {/* Left: Standard Format */}
                    <div style={{
                      background: "#0f172a",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid #1e293b",
                      overflow: "hidden",
                      boxShadow: "var(--shadow-md)"
                    }}>
                      <div style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "0.75rem 1rem",
                        background: "#1e293b",
                        borderBottom: "1px solid #334155"
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span style={{ fontSize: "1rem" }}>📋</span>
                          <span style={{ fontSize: "0.85rem", fontWeight: "700", color: "#f8fafc" }}>
                            Standard Format (Canonical Enterprise)
                          </span>
                        </div>
                        <span style={{ fontSize: "0.72rem", background: "#334155", color: "#94a3b8", padding: "0.2rem 0.5rem", borderRadius: "4px", fontFamily: "var(--font-mono)" }}>
                          response_type=standard
                        </span>
                      </div>
                      <pre style={{
                        margin: 0,
                        padding: "1rem",
                        maxHeight: "520px",
                        overflowY: "auto",
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.8rem",
                        lineHeight: 1.5,
                        color: "#e2e8f0",
                        background: "#0f172a"
                      }}>
                        <code>{JSON.stringify(containerTelemetry.standard, null, 2)}</code>
                      </pre>
                    </div>

                    {/* Right: Mobile-App Format */}
                    <div style={{
                      background: "#0f172a",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid #1e293b",
                      overflow: "hidden",
                      boxShadow: "var(--shadow-md)"
                    }}>
                      <div style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "0.75rem 1rem",
                        background: "#1e293b",
                        borderBottom: "1px solid #334155"
                      }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span style={{ fontSize: "1rem" }}>📱</span>
                          <span style={{ fontSize: "0.85rem", fontWeight: "700", color: "#38bdf8" }}>
                            Mobile-App Format (Flat Lightweight)
                          </span>
                        </div>
                        <span style={{ fontSize: "0.72rem", background: "#0369a1", color: "#bae6fd", padding: "0.2rem 0.5rem", borderRadius: "4px", fontFamily: "var(--font-mono)" }}>
                          response_type=mobile-app
                        </span>
                      </div>
                      <pre style={{
                        margin: 0,
                        padding: "1rem",
                        maxHeight: "520px",
                        overflowY: "auto",
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.8rem",
                        lineHeight: 1.5,
                        color: "#e2e8f0",
                        background: "#0f172a"
                      }}>
                        <code>{JSON.stringify(containerTelemetry.mobileApp, null, 2)}</code>
                      </pre>
                    </div>
                  </div>
                )}

                {/* 2. FULL STANDARD FORMAT */}
                {formatMode === "standard" && (
                  <div style={{
                    background: "#0f172a",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid #1e293b",
                    overflow: "hidden",
                    boxShadow: "var(--shadow-md)"
                  }}>
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "0.75rem 1.25rem",
                      background: "#1e293b",
                      borderBottom: "1px solid #334155"
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span style={{ fontSize: "1.1rem" }}>📋</span>
                        <span style={{ fontSize: "0.92rem", fontWeight: "700", color: "#f8fafc" }}>
                          Standard Enterprise Response Schema
                        </span>
                        <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                          (Includes full carrier metadata, nested coordinates, and multi-provider agent audit trail)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(containerTelemetry.standard, "standard")}
                        className="btn btn-secondary btn-sm"
                      >
                        {copiedFormat === "standard" ? "✓ Copied" : "Copy Payload"}
                      </button>
                    </div>
                    <pre style={{
                      margin: 0,
                      padding: "1.25rem",
                      maxHeight: "580px",
                      overflowY: "auto",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.85rem",
                      lineHeight: 1.55,
                      color: "#e2e8f0",
                      background: "#0f172a"
                    }}>
                      <code>{JSON.stringify(containerTelemetry.standard, null, 2)}</code>
                    </pre>
                  </div>
                )}

                {/* 3. FULL MOBILE-APP FORMAT */}
                {formatMode === "mobile" && (
                  <div style={{
                    background: "#0f172a",
                    borderRadius: "var(--radius-md)",
                    border: "1px solid #1e293b",
                    overflow: "hidden",
                    boxShadow: "var(--shadow-md)"
                  }}>
                    <div style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "0.75rem 1.25rem",
                      background: "#1e293b",
                      borderBottom: "1px solid #334155"
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span style={{ fontSize: "1.1rem" }}>📱</span>
                        <span style={{ fontSize: "0.92rem", fontWeight: "700", color: "#38bdf8" }}>
                          Mobile-App Flat Response Schema
                        </span>
                        <span style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                          (Optimized for mobile clients: flat structure, direct lat/lng per event, ~54% smaller size)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => copyToClipboard(containerTelemetry.mobileApp, "mobile")}
                        className="btn btn-secondary btn-sm"
                      >
                        {copiedFormat === "mobile" ? "✓ Copied" : "Copy Payload"}
                      </button>
                    </div>
                    <pre style={{
                      margin: 0,
                      padding: "1.25rem",
                      maxHeight: "580px",
                      overflowY: "auto",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.85rem",
                      lineHeight: 1.55,
                      color: "#e2e8f0",
                      background: "#0f172a"
                    }}>
                      <code>{JSON.stringify(containerTelemetry.mobileApp, null, 2)}</code>
                    </pre>
                  </div>
                )}

                {/* 4. VISUAL TIMELINE EVENTS */}
                {formatMode === "timeline" && (
                  <div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                      <h3 style={{ fontSize: "1.1rem", fontWeight: "700", color: "var(--text-main)" }}>
                        🕒 Chronological Milestone Events (Descending Order)
                      </h3>
                      <span className="badge badge-tier">Live Telemetry Model</span>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                      {containerTelemetry.standard.events.map((ev, idx) => {
                        const isLatest = idx === 0;
                        const t = new Date(ev.event_time);
                        const dateStr = !isNaN(t.getTime()) ? t.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "-";
                        const timeStr = !isNaN(t.getTime()) ? t.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" }) : "-";

                        return (
                          <div
                            key={idx}
                            style={{
                              display: "flex",
                              gap: "1.5rem",
                              padding: "1rem 1.25rem",
                              background: isLatest ? "#eff6ff" : "var(--bg-surface)",
                              border: `1px solid ${isLatest ? "#bfdbfe" : "var(--border-subtle)"}`,
                              borderRadius: "var(--radius-md)"
                            }}
                          >
                            <div style={{ minWidth: "120px" }}>
                              <div style={{ fontSize: "0.85rem", fontWeight: "700", color: "var(--text-main)" }}>{dateStr}</div>
                              <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{timeStr}</div>
                            </div>
                            <div style={{ flex: 1 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.3rem" }}>
                                <span style={{ fontWeight: "700", fontSize: "0.95rem", color: isLatest ? "var(--accent-blue)" : "var(--text-main)" }}>
                                  {ev.status_message}
                                </span>
                                {isLatest && <span className="badge badge-success" style={{ fontSize: "0.62rem" }}>LATEST</span>}
                              </div>
                              {ev.status_code && (
                                <div style={{ fontSize: "0.78rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)", marginBottom: "0.4rem" }}>
                                  STATUS CODE: {ev.status_code}
                                </div>
                              )}
                              <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", fontSize: "0.78rem" }}>
                                {ev.station && <span style={{ background: "#f1f5f9", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>📍 {ev.station}</span>}
                                {ev.coordinates && (
                                  <span style={{ background: "#e0f2fe", color: "#0369a1", padding: "0.2rem 0.5rem", borderRadius: "4px", fontFamily: "var(--font-mono)" }}>
                                    🌐 GPS: {ev.coordinates.lat}, {ev.coordinates.lng} ({ev.coordinates.matched_name})
                                  </span>
                                )}
                                {ev.flight_info && <span style={{ background: "#f1f5f9", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>🚢 {ev.flight_info}</span>}
                                {ev.weight && <span style={{ background: "#f1f5f9", padding: "0.2rem 0.5rem", borderRadius: "4px" }}>⚖️ {ev.weight} KG</span>}
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

          </div>
        </div>
      </section>

      {/* Carrier Network Coverage Grid */}
      <section id="network" style={{ padding: "4rem 0", background: "#ffffff", borderTop: "1px solid var(--border-subtle)", borderBottom: "1px solid var(--border-subtle)" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
            <span className="badge badge-tier" style={{ marginBottom: "0.5rem" }}>Coverage Directory</span>
            <h2 style={{ fontSize: "2rem", fontWeight: "800", color: "#0f172a" }}>Universal Carrier Network Connectivity</h2>
            <p style={{ color: "var(--text-muted)", fontSize: "1rem" }}>Single standard JSON response regardless of carrier API protocol or EDI format.</p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "1rem" }}>
            {[
              { code: "MSC", name: "Mediterranean Shipping Co", mode: "SEA", latency: "380ms", status: "HEALTHY" },
              { code: "MSK", name: "Maersk Line & Hamburg Süd", mode: "SEA", latency: "420ms", status: "HEALTHY" },
              { code: "CMA", name: "CMA CGM Group", mode: "SEA", latency: "510ms", status: "HEALTHY" },
              { code: "HLC", name: "Hapag-Lloyd Container", mode: "SEA", latency: "460ms", status: "HEALTHY" },
              { code: "ONE", name: "Ocean Network Express", mode: "SEA", latency: "390ms", status: "HEALTHY" },
              { code: "COS", name: "COSCO Shipping Lines", mode: "SEA", latency: "540ms", status: "HEALTHY" },
              { code: "CX", name: "Cathay Pacific Cargo", mode: "AIR", latency: "290ms", status: "HEALTHY" },
              { code: "EK", name: "Emirates SkyCargo", mode: "AIR", latency: "320ms", status: "HEALTHY" },
              { code: "SQ", name: "Singapore Airlines Cargo", mode: "AIR", latency: "340ms", status: "HEALTHY" },
              { code: "LH", name: "Lufthansa Cargo AG", mode: "AIR", latency: "310ms", status: "HEALTHY" },
              { code: "QR", name: "Qatar Airways Cargo", mode: "AIR", latency: "370ms", status: "HEALTHY" },
              { code: "TK", name: "Turkish Cargo", mode: "AIR", latency: "410ms", status: "HEALTHY" },
            ].map((carrier) => (
              <div key={carrier.code} className="card" style={{ padding: "1.2rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className={`badge badge-${carrier.mode.toLowerCase()}`}>{carrier.mode}</span>
                  <span style={{ fontSize: "0.75rem", color: "#15803d", fontWeight: "700" }}>● {carrier.status}</span>
                </div>
                <div style={{ fontWeight: "700", fontSize: "1rem", color: "var(--text-main)" }}>{carrier.name}</div>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                  <span>Code: <strong>{carrier.code}</strong></span>
                  <span>Avg Latency: <strong>{carrier.latency}</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Developer API Quickstart */}
      <section id="code" style={{ padding: "4rem 0", background: "var(--bg-primary)" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
            <span className="badge badge-air" style={{ marginBottom: "0.5rem" }}>Developer Experience</span>
            <h2 style={{ fontSize: "2rem", fontWeight: "800", color: "#0f172a" }}>Integrate in Under 5 Minutes</h2>
            <p style={{ color: "var(--text-muted)", fontSize: "1rem" }}>Pass an AWB or Container Number with your API key to receive instant normalized JSON.</p>
          </div>

          <div className="card" style={{ maxWidth: "800px", margin: "0 auto", padding: 0, overflow: "hidden", boxShadow: "var(--shadow-lg)" }}>
            <div style={{ display: "flex", borderBottom: "1px solid var(--border-subtle)", background: "var(--bg-secondary)" }}>
              {["curl", "python", "javascript", "go"].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveCodeTab(tab)}
                  style={{
                    padding: "0.75rem 1.5rem",
                    border: "none",
                    background: activeCodeTab === tab ? "#ffffff" : "transparent",
                    borderBottom: activeCodeTab === tab ? "2px solid var(--accent-blue)" : "none",
                    fontWeight: activeCodeTab === tab ? "700" : "500",
                    color: activeCodeTab === tab ? "var(--accent-blue)" : "var(--text-secondary)",
                    cursor: "pointer",
                    textTransform: "uppercase",
                    fontSize: "0.85rem"
                  }}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div style={{ padding: "1.5rem", background: "#ffffff", fontFamil: "var(--font-mono)", fontSize: "0.88rem", overflowX: "auto" }}>
              <pre style={{ margin: 0 }}>
                <code>
                  {activeCodeTab === "curl" && `curl -X POST "http://localhost:8000/api/v1/track" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: cargotrk_live_your_api_key_here" \\
  -d '{
    "tracking_number": "MSMU6484830"
  }'`}
                  {activeCodeTab === "python" && `import requests

url = "http://localhost:8000/api/v1/track"
headers = {
    "X-API-Key": "cargotrk_live_your_api_key_here",
    "Content-Type": "application/json"
}
payload = {"tracking_number": "MSMU6484830"}

response = requests.post(url, json=payload, headers=headers)
data = response.json()
print("Mode:", data["mode"])
print("Status:", data["status"])
for event in data["events"]:
    print(f"{event['event_time']} - {event['status_message']}")`}
                  {activeCodeTab === "javascript" && `const response = await fetch("http://localhost:8000/api/v1/track", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": "cargotrk_live_your_api_key_here"
  },
  body: JSON.stringify({ tracking_number: "MSMU6484830" })
});
const data = await response.json();
console.log(data.status, data.events);`}
                  {activeCodeTab === "go" && `package main

import (
    "bytes"
    "fmt"
    "net/http"
)

func main() {
    body := []byte(\`{"tracking_number": "MSMU6484830"}\`)
    req, _ := http.NewRequest("POST", "http://localhost:8000/api/v1/track", bytes.NewBuffer(body))
    req.Header.Set("X-API-Key", "cargotrk_live_your_api_key_here")
    req.Header.Set("Content-Type", "application/json")

    client := &http.Client{}
    resp, err := client.Do(req)
    if err == nil {
        fmt.Println("Status:", resp.Status)
    }
}`}
                </code>
              </pre>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" style={{ padding: "4rem 0", background: "#ffffff", borderTop: "1px solid var(--border-subtle)" }}>
        <div className="container">
          <div style={{ textAlign: "center", marginBottom: "3rem" }}>
            <span className="badge badge-tier" style={{ marginBottom: "0.5rem" }}>Transparent Billing</span>
            <h2 style={{ fontSize: "2rem", fontWeight: "800", color: "#0f172a" }}>Metered Enterprise Subscription Tiers</h2>
            <p style={{ color: "var(--text-muted)", fontSize: "1rem" }}>Scale from early integration testing to high-throughput multi-carrier TMS logistics.</p>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1.5rem" }}>
            {[
              { tier: "Developer", price: "$0", period: "/mo", tracks: "100 tracks / mo", rpm: "10 RPM", keys: "2 API Keys", features: ["Single Live Tracking", "Universal Carrier Fallback", "Standard REST APIs"], cta: "Get Developer Key", action: () => setRegisterModalOpen(true) },
              { tier: "Growth", price: "$199", period: "/mo", tracks: "2,500 tracks / mo", rpm: "60 RPM", keys: "10 API Keys", features: ["Batch CSV Tracking", "Webhook Telemetry Delivery", "Sub-second Fallback"], cta: "Start Growth Plan", featured: true, action: () => setRegisterModalOpen(true) },
              { tier: "Business", price: "$699", period: "/mo", tracks: "15,000 tracks / mo", rpm: "300 RPM", keys: "25 API Keys", features: ["Batch Tracking CSV Ingest", "Priority Carrier SLA", "Team RBAC Management"], cta: "Start Business Plan", action: () => setRegisterModalOpen(true) },
              { tier: "Enterprise", price: "$2,499", period: "/mo", tracks: "1M+ tracks / mo", rpm: "1,200 RPM", keys: "Unlimited Keys", features: ["Custom Credentials Vault", "Dedicated SLA & 99.9% Uptime", "Automated High-Volume Retries"], cta: "Contact Enterprise", action: () => setRegisterModalOpen(true) },
            ].map((plan) => (
              <div
                key={plan.tier}
                className="card"
                style={{
                  padding: "2rem 1.5rem",
                  display: "flex",
                  flexDirection: "column",
                  border: plan.featured ? "2px solid var(--accent-blue)" : "1px solid var(--border-subtle)",
                  position: "relative"
                }}
              >
                {plan.featured && (
                  <span className="badge badge-air" style={{ position: "absolute", top: "-12px", left: "50%", transform: "translateX(-50%)" }}>
                    MOST POPULAR
                  </span>
                )}
                <h3 style={{ fontSize: "1.25rem", fontWeight: "800", color: "var(--text-main)", marginBottom: "0.25rem" }}>{plan.tier}</h3>
                <div style={{ display: "flex", alignItems: "baseline", gap: "0.25rem", margin: "1rem 0" }}>
                  <span style={{ fontSize: "2.25rem", fontWeight: "800", color: "var(--text-main)" }}>{plan.price}</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>{plan.period}</span>
                </div>
                <div style={{ padding: "0.5rem 0", borderTop: "1px solid var(--border-subtle)", borderBottom: "1px solid var(--border-subtle)", marginBottom: "1rem", fontSize: "0.85rem", fontWeight: "600", color: "var(--accent-blue)" }}>
                  {plan.tracks} • {plan.rpm}
                </div>
                <ul style={{ listStyle: "none", padding: 0, margin: "0 0 1.5rem", display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.85rem", color: "var(--text-secondary)", flex: 1 }}>
                  {plan.features.map((feat, idx) => (
                    <li key={idx} style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                      <span style={{ color: "var(--accent-emerald)" }}>✓</span> {feat}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={plan.action}
                  className={`btn ${plan.featured ? "btn-primary" : "btn-secondary"}`}
                  style={{ width: "100%" }}
                >
                  {plan.cta}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ marginTop: "auto", background: "#ffffff", borderTop: "1px solid var(--border-subtle)", padding: "2rem 0" }}>
        <div className="container" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem", fontSize: "0.85rem", color: "var(--text-muted)" }}>
          <div>© 2026 CargoTrk Inc. All rights reserved. Enterprise Multi-Tenant Cargo Intelligence Platform.</div>
          <div style={{ display: "flex", gap: "1.5rem" }}>
            <Link href="/portal" style={{ color: "var(--accent-blue)", fontWeight: "600" }}>Customer Portal</Link>
            <Link href="/staff" style={{ color: "var(--accent-rose)", fontWeight: "600" }}>Superadmin Backoffice</Link>
            <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" style={{ color: "var(--text-secondary)" }}>API Docs (OpenAPI)</a>
          </div>
        </div>
      </footer>

      {/* Auth Required Warning Modal */}
      {authRequiredModalOpen && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: "460px", textAlign: "center" }}>
            <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>🔒</div>
            <h3 style={{ fontSize: "1.25rem", fontWeight: "800", color: "var(--text-main)", marginBottom: "0.5rem" }}>
              Authentication Required
            </h3>
            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "1.5rem" }}>
              Live carrier tracking is a metered enterprise service. To track shipments, please enter your organization API key or sign in to your tenant account.
            </p>
            <div style={{ display: "flex", gap: "0.75rem", justifyContent: "center" }}>
              <button
                onClick={() => { setAuthRequiredModalOpen(false); setRegisterModalOpen(true); }}
                className="btn btn-primary"
              >
                Get Free API Key
              </button>
              <button
                onClick={() => { setAuthRequiredModalOpen(false); setLoginModalOpen(true); }}
                className="btn btn-secondary"
              >
                Sign In
              </button>
              <button
                onClick={() => setAuthRequiredModalOpen(false)}
                className="btn btn-outline"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Login Modal */}
      {loginModalOpen && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3 className="modal-title"><span>🔐</span> Sign In to CargoTrk</h3>
              <button className="modal-close" onClick={() => setLoginModalOpen(false)}>&times;</button>
            </div>

            <form onSubmit={handleLogin}>
              {loginError && (
                <div style={{ padding: "0.75rem", background: "#fef2f2", color: "#b91c1c", borderRadius: "6px", fontSize: "0.85rem", marginBottom: "1rem" }}>
                  {loginError}
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                  type="email"
                  className="form-input"
                  required
                  placeholder="admin@apexlogistics.com"
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
                  placeholder="••••••••••••"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                />
              </div>

              <div className="form-group" style={{ flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  id="staffCheck"
                  checked={loginAsStaff}
                  onChange={(e) => setLoginAsStaff(e.target.checked)}
                />
                <label htmlFor="staffCheck" style={{ fontSize: "0.85rem", color: "var(--text-secondary)", cursor: "pointer" }}>
                  Sign in to <strong>Superadmin &amp; Staff Backoffice</strong>
                </label>
              </div>

              <div className="modal-footer" style={{ marginTop: "1.5rem" }}>
                <button type="button" className="btn btn-secondary" onClick={() => setLoginModalOpen(false)}>Cancel</button>
                <button type="submit" disabled={loginLoading} className="btn btn-primary">
                  {loginLoading ? "Authenticating..." : "Sign In"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Register Organization Modal */}
      {registerModalOpen && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div className="modal-header">
              <h3 className="modal-title"><span>⚡</span> Onboard Enterprise Organization</h3>
              <button className="modal-close" onClick={() => { setRegisterModalOpen(false); setNewGeneratedKey(null); }}>&times;</button>
            </div>

            {!newGeneratedKey ? (
              <form onSubmit={handleRegister}>
                {regError && (
                  <div style={{ padding: "0.75rem", background: "#fef2f2", color: "#b91c1c", borderRadius: "6px", fontSize: "0.85rem", marginBottom: "1rem" }}>
                    {regError}
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">Organization Legal Name</label>
                  <input
                    type="text"
                    className="form-input"
                    required
                    placeholder="Apex Global Freight"
                    value={regOrgName}
                    onChange={(e) => setRegOrgName(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Tenant Slug (Identifier)</label>
                  <input
                    type="text"
                    className="form-input"
                    required
                    placeholder="apex-global"
                    value={regSlug}
                    onChange={(e) => setRegSlug(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Admin Email</label>
                  <input
                    type="email"
                    className="form-input"
                    required
                    placeholder="ops@apexlogistics.com"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Password</label>
                  <input
                    type="password"
                    className="form-input"
                    required
                    placeholder="••••••••••••"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Initial Subscription Tier</label>
                  <select className="form-select" value={regTier} onChange={(e) => setRegTier(e.target.value)}>
                    <option value="developer">Developer Plan (100 free tracks/mo)</option>
                    <option value="growth">Growth Plan ($199/mo - 2,500 tracks)</option>
                    <option value="business">Business Plan ($699/mo - 15,000 tracks)</option>
                    <option value="enterprise">Enterprise Plan ($2,499/mo - 1M tracks)</option>
                  </select>
                </div>

                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setRegisterModalOpen(false)}>Cancel</button>
                  <button type="submit" disabled={regLoading} className="btn btn-primary">
                    {regLoading ? "Creating Organization..." : "Generate Production Key"}
                  </button>
                </div>
              </form>
            ) : (
              <div style={{ textAlign: "center", padding: "1rem 0" }}>
                <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>🎉</div>
                <h4 style={{ fontSize: "1.25rem", fontWeight: "800", color: "var(--text-main)", marginBottom: "0.5rem" }}>
                  Organization Successfully Onboarded!
                </h4>
                <p style={{ fontSize: "0.88rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
                  Your production API key has been created. Store it securely; this secret cannot be viewed again:
                </p>

                <div className="secret-reveal-card">
                  <span>{newGeneratedKey}</span>
                  <button
                    onClick={() => { navigator.clipboard.writeText(newGeneratedKey); showToast("Copied API Key to clipboard!", "success"); }}
                    className="btn btn-secondary btn-sm"
                  >
                    Copy
                  </button>
                </div>

                <div style={{ marginTop: "1.5rem", display: "flex", justifyContent: "center", gap: "0.75rem" }}>
                  <button
                    onClick={() => { setRegisterModalOpen(false); setNewGeneratedKey(null); handleTrackSubmit(); }}
                    className="btn btn-primary"
                  >
                    Track Shipment Now ➔
                  </button>
                  <Link href="/portal" className="btn btn-secondary">
                    Open Customer Portal
                  </Link>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
