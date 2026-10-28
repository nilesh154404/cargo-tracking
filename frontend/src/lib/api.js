/**
 * Enterprise Cargo Intelligence API Client for Next.js
 */
import { getMockContainerTelemetry } from "./mockContainers";

const API_BASE = "/api/v1";

export const STORAGE_KEYS = {
  TOKEN: "cargotrk_auth_token",
  USER: "cargotrk_user_profile",
  TENANT: "cargotrk_tenant_context",
  STAFF_TOKEN: "cargotrk_staff_token",
  USER_API_KEY: "cargotrk_user_api_key",
};

export async function apiRequest(endpoint, options = {}) {
  const url = endpoint.startsWith("http") ? endpoint : `${API_BASE}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  // Attach auth if available
  if (typeof window !== "undefined") {
    // If explicit API Key header is passed in options, keep it.
    // Otherwise, check for JWT token:
    if (!headers["X-API-Key"]) {
      const staffToken = localStorage.getItem(STORAGE_KEYS.STAFF_TOKEN);
      const userToken = localStorage.getItem(STORAGE_KEYS.TOKEN);
      const activeToken = options.useStaffAuth ? staffToken : (userToken || staffToken);

      if (activeToken) {
        headers["Authorization"] = `Bearer ${activeToken}`;
      } else {
        // Check for stored user API key if any
        const savedApiKey = localStorage.getItem(STORAGE_KEYS.USER_API_KEY);
        if (savedApiKey) {
          headers["X-API-Key"] = savedApiKey;
        }
      }
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    if (typeof window !== "undefined" && !endpoint.includes("/auth/login")) {
      localStorage.removeItem(STORAGE_KEYS.TOKEN);
      localStorage.removeItem(STORAGE_KEYS.USER);
      localStorage.removeItem(STORAGE_KEYS.TENANT);
    }
    const err = await response.json().catch(() => ({}));
    const error = new Error(err.detail || "Authentication required. Please enter an API key or sign in.");
    error.status = 401;
    throw error;
  }

  if (response.status === 429) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail?.message || "Monthly tracking quota reached. Upgrade your subscription plan.");
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    const msg = typeof err.detail === "string" ? err.detail : (err.detail?.message || "API request failed");
    throw new Error(msg);
  }

  if (response.status === 204) return null;
  return await response.json();
}

// Tracking APIs - strictly secured
export async function trackShipment(paramsOrQuery, customApiKey = null) {
  const headers = {};
  if (customApiKey) {
    headers["X-API-Key"] = customApiKey.trim();
  }
  let bodyPayload = {};
  if (typeof paramsOrQuery === "string") {
    const trimmed = paramsOrQuery.trim();
    bodyPayload = { query: trimmed, tracking_number: trimmed };
  } else if (typeof paramsOrQuery === "object" && paramsOrQuery !== null) {
    bodyPayload = { ...paramsOrQuery };
    if (!bodyPayload.query) {
      bodyPayload.query = (
        bodyPayload.CONTAINER_NO ||
        bodyPayload.container_no ||
        bodyPayload.MAWB_OBL_NO ||
        bodyPayload.mawb_obl_no ||
        ""
      ).trim();
    }
  }
  return apiRequest("/track", {
    method: "POST",
    headers,
    body: JSON.stringify(bodyPayload),
  });
}

export async function batchTrackShipments(items) {
  return apiRequest("/track/batch", {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

export async function getShipmentHistory(limit = 50) {
  return apiRequest(`/shipments?limit=${limit}`);
}

export async function getTrackingInspectionData(trackingNumber) {
  const clean = String(trackingNumber || "").trim().toUpperCase();
  if (!clean) return getMockContainerTelemetry("MSMU6484830");

  try {
    const [stdResp, mobResp, histResp] = await Promise.all([
      apiRequest(`/track/${encodeURIComponent(clean)}?response_type=standard`).catch(() => null),
      apiRequest(`/track/${encodeURIComponent(clean)}?response_type=mobile-app`).catch(() => null),
      apiRequest(`/history/${encodeURIComponent(clean)}?auto_track=false`).catch(() => null),
    ]);

    if (stdResp || mobResp || histResp) {
      const standard = stdResp || histResp || {};
      const mobileApp = mobResp || {};
      const events = standard.events || histResp?.events || [];
      return {
        standard,
        mobileApp,
        events,
        source: "live_backend"
      };
    }
  } catch (err) {
    console.warn("Live inspection telemetry fallback:", err);
  }

  const mock = getMockContainerTelemetry(clean);
  return {
    standard: mock.standard,
    mobileApp: mock.mobileApp,
    events: mock.standard?.events || [],
    source: "mock_engine"
  };
}

// Authentication & Tenant Session APIs
export async function loginUser(email, password) {
  const data = await apiRequest("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  if (typeof window !== "undefined") {
    localStorage.setItem(STORAGE_KEYS.TOKEN, data.access_token);
    if (data.user) {
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(data.user));
      if (data.user.role === "SUPER_ADMIN") {
        localStorage.setItem(STORAGE_KEYS.STAFF_TOKEN, data.access_token);
      }
    }
    if (data.tenant) {
      localStorage.setItem(STORAGE_KEYS.TENANT, JSON.stringify(data.tenant));
    }
  }
  return data;
}

export async function registerOrganization(payload) {
  return apiRequest("/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getTenantProfile() {
  return apiRequest("/auth/me");
}

export async function getTenantUsage() {
  return apiRequest("/subscription/usage");
}

export async function getTenantUsageLogs(params = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", params.limit);
  if (params.offset) query.set("offset", params.offset);
  if (params.mode) query.set("mode", params.mode);
  if (params.status) query.set("status", params.status);
  if (params.carrier_code) query.set("carrier_code", params.carrier_code);
  if (params.search) query.set("search", params.search);
  const qStr = query.toString();
  return apiRequest(`/subscription/usage-records${qStr ? `?${qStr}` : ""}`);
}

export async function getSubscriptionPlans() {
  return apiRequest("/subscription/plans");
}

export async function upgradeSubscriptionPlan(tierCode) {
  return apiRequest("/subscription/upgrade", {
    method: "POST",
    body: JSON.stringify({ tier_code: tierCode }),
  });
}

// API Key Management APIs
export async function listApiKeys() {
  return apiRequest("/api-keys");
}

export async function createApiKey(name, scopes = ["tracking:live", "tracking:read", "shipments:batch"]) {
  return apiRequest("/api-keys", {
    method: "POST",
    body: JSON.stringify({ name, scopes }),
  });
}

export async function revokeApiKey(keyId) {
  return apiRequest(`/api-keys/${keyId}`, {
    method: "DELETE",
  });
}

// Superadmin & Staff APIs
export async function getAdminPlatformStats() {
  return apiRequest("/admin/stats", { useStaffAuth: true });
}

export async function listAdminTenants() {
  return apiRequest("/admin/tenants", { useStaffAuth: true });
}

export async function onboardNewTenant(payload) {
  return apiRequest("/admin/tenants", {
    method: "POST",
    useStaffAuth: true,
    body: JSON.stringify(payload),
  });
}

export async function updateTenantQuota(tenantId, payload) {
  return apiRequest(`/admin/tenants/${tenantId}/quota`, {
    method: "POST",
    useStaffAuth: true,
    body: JSON.stringify(payload),
  });
}

export async function impersonateTenant(tenantId) {
  return apiRequest(`/admin/tenants/${tenantId}/impersonate`, {
    method: "POST",
    useStaffAuth: true,
  });
}

export async function getCarrierHealthSla() {
  return apiRequest("/admin/carriers", { useStaffAuth: true });
}

export async function getProviderExecutionLogs(limit = 50) {
  return apiRequest(`/admin/logs?limit=${limit}`, { useStaffAuth: true });
}

export async function getAdminUsageLogs(params = {}) {
  const query = new URLSearchParams();
  if (params.limit) query.set("limit", params.limit);
  if (params.offset) query.set("offset", params.offset);
  if (params.tenant_id) query.set("tenant_id", params.tenant_id);
  if (params.mode) query.set("mode", params.mode);
  if (params.search) query.set("search", params.search);
  const qStr = query.toString();
  return apiRequest(`/admin/usage-records${qStr ? `?${qStr}` : ""}`, { useStaffAuth: true });
}
