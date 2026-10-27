/**
 * Decoupled API Client for Cargo Intelligence Platform
 */
class ApiClient {
  constructor() {
    this.baseUrl = window.APP_CONFIG.API_BASE_URL;
  }

  getHeaders(customHeaders = {}) {
    const headers = {
      "Content-Type": "application/json",
      ...customHeaders
    };

    // Check for active JWT session token
    const token = localStorage.getItem(window.APP_CONFIG.STORAGE_KEYS.AUTH_TOKEN);
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    } else {
      // Fallback to demo API key for public sandbox queries
      headers["X-API-Key"] = window.APP_CONFIG.DEMO_API_KEY;
    }

    return headers;
  }

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith("http") ? endpoint : `${this.baseUrl}${endpoint}`;
    const headers = this.getHeaders(options.headers || {});
    const config = {
      ...options,
      headers
    };

    try {
      const response = await fetch(url, config);

      if (response.status === 429) {
        const errorData = await response.json().catch(() => ({}));
        window.dispatchEvent(new CustomEvent("cargotrk:quota_exceeded", { detail: errorData }));
        throw new Error(errorData.detail?.message || "Monthly tracking quota exceeded. Please upgrade plan.");
      }

      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent("cargotrk:unauthorized"));
      }

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({ detail: response.statusText }));
        const msg = typeof errJson.detail === "string" ? errJson.detail : (errJson.detail?.message || "API Request Failed");
        throw new Error(msg);
      }

      if (response.status === 204) return null;
      return await response.json();
    } catch (err) {
      console.error(`[API Error] ${options.method || 'GET'} ${url}:`, err);
      throw err;
    }
  }

  // Tracking API
  async track(trackingNumber, carrierCode = null, customerReference = null) {
    const trimmed = trackingNumber.trim();
    return this.request("/track", {
      method: "POST",
      body: JSON.stringify({
        query: trimmed,
        tracking_number: trimmed,
        carrier_code: carrierCode,
        customer_reference: customerReference
      })
    });
  }

  async batchTrack(shipments) {
    return this.request("/track/batch", {
      method: "POST",
      body: JSON.stringify({ shipments })
    });
  }

  async getShipments(limit = 50, mode = null, status = null) {
    let q = `?limit=${limit}`;
    if (mode) q += `&mode=${mode}`;
    if (status) q += `&status=${status}`;
    return this.request(`/shipments${q}`);
  }

  // Developer API Keys
  async getApiKeys() {
    return this.request("/api-keys");
  }

  async createApiKey(name, scopes = ["tracking:live", "tracking:read", "shipments:batch"]) {
    return this.request("/api-keys", {
      method: "POST",
      body: JSON.stringify({ name, scopes })
    });
  }

  async revokeApiKey(keyId) {
    return this.request(`/api-keys/${keyId}`, {
      method: "DELETE"
    });
  }

  // Subscriptions & Usage
  async getUsage() {
    return this.request("/subscription/usage");
  }

  async getPlans() {
    return this.request("/subscription/plans");
  }

  async upgradePlan(tierCode) {
    return this.request("/subscription/upgrade", {
      method: "POST",
      body: JSON.stringify({ tier_code: tierCode })
    });
  }

  // Carriers & Providers
  async getCarriers() {
    return this.request("/carriers");
  }

  async getProvidersHealth() {
    return this.request("/providers/health");
  }

  // Superadmin & Staff Operations
  async getAdminStats() {
    return this.request("/admin/stats");
  }

  async getAdminTenants() {
    return this.request("/admin/tenants");
  }

  async updateTenantQuota(tenantId, payload) {
    return this.request(`/admin/tenants/${tenantId}/quota`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  }

  async getAdminLogs(limit = 50) {
    return this.request(`/admin/logs?limit=${limit}`);
  }
}

window.apiClient = new ApiClient();
