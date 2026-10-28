"use client";

import { useState } from "react";

export default function TrackingInspectionModal({
  isOpen,
  onClose,
  logItem,
  data,
  loading = false,
  activeView = "timeline",
  setActiveView,
  onRetrack,
}) {
  const [copiedView, setCopiedView] = useState(null);

  if (!isOpen) return null;

  const trackingNumber =
    logItem?.tracking_number ||
    logItem?.awb_number ||
    logItem?.container_number ||
    data?.standard?.tracking_number ||
    data?.standard?.container_no ||
    "--";

  const mode =
    logItem?.transport_mode ||
    data?.standard?.mode ||
    data?.standard?.transport_mode ||
    "SEA";

  const status =
    logItem?.status ||
    data?.standard?.status ||
    data?.mobileApp?.quick_status ||
    "IN_TRANSIT";

  const carrierName =
    logItem?.carrier_name ||
    data?.standard?.carrier?.name ||
    logItem?.carrier_code ||
    "--";

  const carrierCode =
    logItem?.carrier_code ||
    data?.standard?.carrier?.code ||
    "";

  const providerUsed =
    logItem?.provider_used ||
    data?.standard?.telemetry_source ||
    data?.source ||
    "live_carrier_api";

  const credits = logItem?.credits_consumed ?? 1;

  const events =
    data?.events ||
    data?.standard?.events ||
    data?.standard?.milestones ||
    [];

  const origin =
    data?.standard?.origin ||
    (logItem?.origin_port ? { name: logItem.origin_port } : null);

  const destination =
    data?.standard?.destination ||
    (logItem?.dest_port ? { name: logItem.dest_port } : null);

  const handleCopy = (obj, key) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(JSON.stringify(obj, null, 2));
      setCopiedView(key);
      setTimeout(() => setCopiedView(null), 2500);
    }
  };

  const isDelivered = String(status).toUpperCase().includes("DELIVERED");
  const isInTransit =
    String(status).toUpperCase().includes("TRANSIT") ||
    String(status).toUpperCase().includes("DEPART") ||
    String(status).toUpperCase().includes("SAIL");

  return (
    <div
      className="modal-backdrop"
      style={{ zIndex: 1200, padding: "1rem" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-card modal-card-lg" style={{ maxHeight: "92vh" }}>
        {/* Modal Header */}
        <div
          className="modal-header"
          style={{
            background: "#ffffff",
            borderBottom: "1px solid var(--border-subtle)",
            padding: "1.1rem 1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "0.75rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
            <span style={{ fontSize: "1.4rem" }}>📦</span>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                <h3 style={{ margin: 0, fontSize: "1.2rem", fontWeight: "800", color: "var(--text-main)", letterSpacing: "-0.01em" }}>
                  {trackingNumber}
                </h3>
                <span className={`badge badge-${mode.toLowerCase()}`} style={{ fontSize: "0.72rem", padding: "0.2rem 0.5rem" }}>
                  {mode === "AIR" ? "✈️ AIR AWB" : "🚢 SEA CONTAINER"}
                </span>
                <span
                  className={`badge ${isDelivered ? "badge-success" : isInTransit ? "badge-info" : "badge-warning"}`}
                  style={{ fontSize: "0.72rem", padding: "0.2rem 0.5rem" }}
                >
                  {status}
                </span>
              </div>
              <p style={{ margin: "2px 0 0 0", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                Carrier: <strong>{carrierName}</strong> {carrierCode && `(${carrierCode})`} • Provider:{" "}
                <code style={{ fontSize: "0.75rem", background: "#f1f5f9", padding: "1px 5px", borderRadius: "3px" }}>
                  {providerUsed}
                </code>
              </p>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            {onRetrack && (
              <button
                onClick={() => onRetrack(trackingNumber, mode, carrierCode)}
                className="btn btn-secondary btn-sm"
                style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem" }}
                title="Re-track in Live Tracker tab"
              >
                ⚡ Live Track
              </button>
            )}
            <button
              className="modal-close"
              onClick={onClose}
              style={{ fontSize: "1.6rem", padding: "0 0.5rem", cursor: "pointer", background: "none", border: "none" }}
              aria-label="Close modal"
            >
              &times;
            </button>
          </div>
        </div>

        {/* View Switcher Tabs */}
        <div className="inspect-tabs-bar">
          <button
            className={`inspect-tab-btn ${activeView === "timeline" ? "active" : ""}`}
            onClick={() => setActiveView("timeline")}
          >
            <span>📅</span> Timeline & Milestones ({events.length})
          </button>
          <button
            className={`inspect-tab-btn ${activeView === "standard" ? "active" : ""}`}
            onClick={() => setActiveView("standard")}
          >
            <span>🌐</span> Standard Enterprise Format (JSON)
          </button>
          <button
            className={`inspect-tab-btn ${activeView === "mobile" ? "active" : ""}`}
            onClick={() => setActiveView("mobile")}
          >
            <span>📱</span> Mobile App Format (JSON)
          </button>
          <button
            className={`inspect-tab-btn ${activeView === "audit" ? "active" : ""}`}
            onClick={() => setActiveView("audit")}
          >
            <span>🛡️</span> Audit Log & Meta Details
          </button>
        </div>

        {/* Body Content */}
        <div className="modal-body-scroll">
          {loading ? (
            <div style={{ textAlign: "center", padding: "3rem 1rem" }}>
              <div className="spinner" style={{ margin: "0 auto 1rem auto" }}></div>
              <h4 style={{ fontSize: "1rem", color: "var(--text-main)", marginBottom: "0.25rem" }}>
                Querying Telemetry & Building Multi-Format View...
              </h4>
              <p style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
                Retrieving live carrier response payloads and historical milestones.
              </p>
            </div>
          ) : (
            <>
              {/* VIEW 1: TIMELINE & MILESTONES */}
              {activeView === "timeline" && (
                <div>
                  {/* Route Summary Card */}
                  <div
                    style={{
                      background: "linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%)",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid #dbeafe",
                      padding: "1.25rem",
                      marginBottom: "1.5rem",
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                      gap: "1rem",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <span style={{ fontSize: "0.72rem", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.05em" }}>
                        Origin Port / Location
                      </span>
                      <div style={{ fontWeight: "700", color: "#1e293b", fontSize: "0.95rem", marginTop: "2px" }}>
                        📍 {origin?.name || origin?.port_name || logItem?.origin_port || "Origin Gateway"}
                      </div>
                      {(origin?.code || origin?.locode) && (
                        <div style={{ fontSize: "0.75rem", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                          UN/LOCODE: {origin?.code || origin?.locode}
                        </div>
                      )}
                      {origin?.coordinates?.lat && (
                        <a
                          href={`https://www.google.com/maps?q=${origin.coordinates.lat},${origin.coordinates.lng}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ fontSize: "0.72rem", color: "var(--brand-primary)", textDecoration: "underline" }}
                        >
                          Map: {origin.coordinates.lat.toFixed(3)}, {origin.coordinates.lng.toFixed(3)} ↗
                        </a>
                      )}
                    </div>

                    <div style={{ textAlign: "center", borderLeft: "1px dashed #cbd5e1", borderRight: "1px dashed #cbd5e1", padding: "0 0.5rem" }}>
                      <span style={{ fontSize: "0.72rem", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.05em" }}>
                        Transit Status
                      </span>
                      <div style={{ fontWeight: "800", color: "var(--brand-primary)", fontSize: "1.05rem", marginTop: "2px" }}>
                        {status}
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "#64748b" }}>
                        {data?.standard?.vessel?.name
                          ? `🚢 ${data.standard.vessel.name}`
                          : data?.standard?.carrier?.vessel
                          ? `🚢 ${data.standard.carrier.vessel}`
                          : mode === "AIR"
                          ? "✈️ Scheduled Flight"
                          : "🚢 Container Vessel"}
                      </div>
                    </div>

                    <div>
                      <span style={{ fontSize: "0.72rem", fontWeight: "700", textTransform: "uppercase", color: "#64748b", letterSpacing: "0.05em" }}>
                        Destination Port / ETA
                      </span>
                      <div style={{ fontWeight: "700", color: "#1e293b", fontSize: "0.95rem", marginTop: "2px" }}>
                        🏁 {destination?.name || destination?.port_name || logItem?.dest_port || "Destination Terminal"}
                      </div>
                      {(destination?.code || destination?.locode) && (
                        <div style={{ fontSize: "0.75rem", color: "#64748b", fontFamily: "var(--font-mono)" }}>
                          UN/LOCODE: {destination?.code || destination?.locode}
                        </div>
                      )}
                      {destination?.coordinates?.lat && (
                        <a
                          href={`https://www.google.com/maps?q=${destination.coordinates.lat},${destination.coordinates.lng}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ fontSize: "0.72rem", color: "var(--brand-primary)", textDecoration: "underline" }}
                        >
                          Map: {destination.coordinates.lat.toFixed(3)}, {destination.coordinates.lng.toFixed(3)} ↗
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Milestones Stepper */}
                  <div style={{ padding: "0.5rem 0.5rem" }}>
                    <h4 style={{ fontSize: "0.95rem", fontWeight: "800", color: "var(--text-main)", marginBottom: "1rem" }}>
                      Chronological Milestone Events ({events.length})
                    </h4>

                    {events.length === 0 ? (
                      <div style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)", fontSize: "0.88rem" }}>
                        No specific granular milestone steps recorded for this query yet.
                      </div>
                    ) : (
                      <div className="telemetry-timeline">
                        {events.map((ev, idx) => {
                          const evStatus = ev.status || ev.event_type || ev.description || "EVENT";
                          const isLast = idx === events.length - 1;
                          const isEvDelivered = String(evStatus).toUpperCase().includes("DELIVERED");
                          const locName =
                            typeof ev.location === "object"
                              ? ev.location?.name || ev.location?.city || ev.location?.code
                              : ev.location || ev.port || "--";
                          const coords = ev.coordinates || ev.location?.coordinates;

                          return (
                            <div
                              key={idx}
                              className={`telemetry-event-item ${idx === 0 ? "active" : isEvDelivered ? "completed" : ""}`}
                            >
                              <div className="telemetry-node-dot" />
                              <div
                                style={{
                                  background: "#ffffff",
                                  border: "1px solid var(--border-subtle)",
                                  borderRadius: "var(--radius-sm)",
                                  padding: "0.85rem 1rem",
                                  boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "flex-start",
                                    flexWrap: "wrap",
                                    gap: "0.5rem",
                                  }}
                                >
                                  <div>
                                    <span
                                      className={`badge ${
                                        isEvDelivered
                                          ? "badge-success"
                                          : idx === 0
                                          ? "badge-info"
                                          : "badge-secondary"
                                      }`}
                                      style={{ fontSize: "0.72rem", marginRight: "0.5rem" }}
                                    >
                                      {evStatus}
                                    </span>
                                    <strong style={{ fontSize: "0.88rem", color: "#1e293b" }}>
                                      {locName}
                                    </strong>
                                  </div>

                                  <span
                                    style={{
                                      fontSize: "0.76rem",
                                      color: "var(--text-muted)",
                                      fontFamily: "var(--font-mono)",
                                    }}
                                  >
                                    🕒 {ev.timestamp || ev.date || ev.event_time || "--"}
                                  </span>
                                </div>

                                {ev.description && ev.description !== evStatus && (
                                  <p style={{ margin: "0.35rem 0 0 0", fontSize: "0.82rem", color: "#475569" }}>
                                    {ev.description}
                                  </p>
                                )}

                                <div
                                  style={{
                                    display: "flex",
                                    gap: "1rem",
                                    marginTop: "0.4rem",
                                    fontSize: "0.75rem",
                                    color: "#64748b",
                                    flexWrap: "wrap",
                                  }}
                                >
                                  {(ev.vessel || ev.voyage || ev.vessel_voyage || ev.flight_number) && (
                                    <span>
                                      🚢 Conveyance: {ev.vessel || ev.voyage || ev.vessel_voyage || ev.flight_number}
                                    </span>
                                  )}
                                  {coords?.lat && (
                                    <a
                                      href={`https://www.google.com/maps?q=${coords.lat},${coords.lng}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      style={{ color: "var(--brand-primary)", textDecoration: "underline" }}
                                    >
                                      📍 Geo: {coords.lat.toFixed(3)}, {coords.lng.toFixed(3)}
                                    </a>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* VIEW 2: STANDARD ENTERPRISE FORMAT */}
              {activeView === "standard" && (
                <div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: "0.75rem",
                      flexWrap: "wrap",
                      gap: "0.5rem",
                    }}
                  >
                    <div>
                      <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: "800", color: "var(--text-main)" }}>
                        Standard Enterprise JSON Schema
                      </h4>
                      <p style={{ margin: "2px 0 0 0", fontSize: "0.78rem", color: "var(--text-muted)" }}>
                        Unified schema conforming to ISO/WCO logistics data specifications with carrier breakdown & geo coordinates.
                      </p>
                    </div>

                    <button
                      onClick={() => handleCopy(data?.standard, "standard")}
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: "0.78rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}
                    >
                      {copiedView === "standard" ? "✅ Copied JSON!" : "📋 Copy Standard JSON"}
                    </button>
                  </div>

                  <div className="code-viewer-container">
                    <div className="code-viewer-header">
                      <span>HTTP 200 OK • application/json • response_type=standard</span>
                      <span>
                        Size: {data?.standard ? `${(JSON.stringify(data.standard).length / 1024).toFixed(1)} KB` : "0 KB"}
                      </span>
                    </div>
                    <pre className="code-viewer-body">
                      {data?.standard ? JSON.stringify(data.standard, null, 2) : "// No standard payload available"}
                    </pre>
                  </div>
                </div>
              )}

              {/* VIEW 3: MOBILE APP FORMAT */}
              {activeView === "mobile" && (
                <div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: "0.75rem",
                      flexWrap: "wrap",
                      gap: "0.5rem",
                    }}
                  >
                    <div>
                      <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: "800", color: "var(--text-main)" }}>
                        Mobile App Lightweight JSON Schema
                      </h4>
                      <p style={{ margin: "2px 0 0 0", fontSize: "0.78rem", color: "var(--text-muted)" }}>
                        Optimized for low-latency bandwidth, push notifications, and mobile dashboards (ETA, progress %, simplified timeline).
                      </p>
                    </div>

                    <button
                      onClick={() => handleCopy(data?.mobileApp, "mobile")}
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: "0.78rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}
                    >
                      {copiedView === "mobile" ? "✅ Copied JSON!" : "📋 Copy Mobile JSON"}
                    </button>
                  </div>

                  <div className="code-viewer-container">
                    <div className="code-viewer-header">
                      <span>HTTP 200 OK • application/json • response_type=mobile-app</span>
                      <span>
                        Size: {data?.mobileApp ? `${(JSON.stringify(data.mobileApp).length / 1024).toFixed(1)} KB` : "0 KB"}
                      </span>
                    </div>
                    <pre className="code-viewer-body" style={{ color: "#a5b4fc" }}>
                      {data?.mobileApp ? JSON.stringify(data.mobileApp, null, 2) : "// No mobile app payload available"}
                    </pre>
                  </div>
                </div>
              )}

              {/* VIEW 4: AUDIT LOG & META */}
              {activeView === "audit" && (
                <div>
                  <h4 style={{ fontSize: "0.95rem", fontWeight: "800", color: "var(--text-main)", marginBottom: "0.75rem" }}>
                    Audit Log & Execution Metadata
                  </h4>

                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
                      gap: "1rem",
                      background: "#f8fafc",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--border-subtle)",
                      padding: "1.25rem",
                    }}
                  >
                    <div>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>
                        Tracking Number
                      </span>
                      <div style={{ fontWeight: "700", color: "var(--text-main)", fontSize: "0.92rem", fontFamily: "var(--font-mono)" }}>
                        {trackingNumber}
                      </div>
                    </div>

                    <div>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>
                        Transport Mode
                      </span>
                      <div style={{ fontWeight: "600", color: "var(--text-main)", fontSize: "0.92rem" }}>
                        {mode === "AIR" ? "✈️ AIR FREIGHT" : "🚢 OCEAN FREIGHT"}
                      </div>
                    </div>

                    <div>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>
                        Carrier
                      </span>
                      <div style={{ fontWeight: "600", color: "var(--text-main)", fontSize: "0.92rem" }}>
                        {carrierName} {carrierCode && `[${carrierCode}]`}
                      </div>
                    </div>

                    <div>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>
                        Telemetric Provider Used
                      </span>
                      <div style={{ fontWeight: "600", color: "var(--text-main)", fontSize: "0.92rem" }}>
                        <code style={{ background: "#e2e8f0", padding: "2px 6px", borderRadius: "4px" }}>
                          {providerUsed}
                        </code>
                      </div>
                    </div>

                    <div>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>
                        Credits Consumed
                      </span>
                      <div style={{ fontWeight: "700", color: "var(--brand-primary)", fontSize: "0.92rem" }}>
                        {credits} credit{credits === 1 ? "" : "s"}
                      </div>
                    </div>

                    <div>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>
                        Request Origin IP
                      </span>
                      <div style={{ fontWeight: "600", color: "var(--text-main)", fontSize: "0.92rem", fontFamily: "var(--font-mono)" }}>
                        {logItem?.request_ip || "127.0.0.1"}
                      </div>
                    </div>

                    <div>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>
                        Timestamp (UTC / Local)
                      </span>
                      <div style={{ fontWeight: "600", color: "var(--text-main)", fontSize: "0.85rem", fontFamily: "var(--font-mono)" }}>
                        {logItem?.created_at || logItem?.timestamp || new Date().toISOString()}
                      </div>
                    </div>

                    <div>
                      <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700" }}>
                        Tenant / Organization
                      </span>
                      <div style={{ fontWeight: "600", color: "var(--text-main)", fontSize: "0.92rem" }}>
                        {logItem?.tenant_name || "Enterprise Workspace"}
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: "1rem" }}>
                    <button
                      onClick={() => handleCopy({ log_audit_record: logItem, inspection: data }, "audit")}
                      className="btn btn-secondary btn-sm"
                      style={{ fontSize: "0.78rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}
                    >
                      {copiedView === "audit" ? "✅ Copied Audit Record!" : "📋 Copy Complete Audit JSON"}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Modal Footer */}
        <div
          className="modal-footer"
          style={{
            borderTop: "1px solid var(--border-subtle)",
            padding: "0.85rem 1.5rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "#ffffff",
          }}
        >
          <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
            Telemetric Engine: <strong>{data?.source === "mock_engine" ? "Synthetic Container Hub" : "Active Carrier REST Engine"}</strong>
          </div>
          <button onClick={onClose} className="btn btn-secondary">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
