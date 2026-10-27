/**
 * Authentication and Session Management
 */
class AuthService {
  constructor() {
    this.keys = window.APP_CONFIG.STORAGE_KEYS;
  }

  getToken() {
    return localStorage.getItem(this.keys.AUTH_TOKEN);
  }

  getUser() {
    try {
      const u = localStorage.getItem(this.keys.USER_PROFILE);
      return u ? JSON.parse(u) : null;
    } catch {
      return null;
    }
  }

  isAuthenticated() {
    return !!this.getToken();
  }

  async login(email, password) {
    const res = await fetch(`${window.APP_CONFIG.API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Invalid email or password");
    }

    const data = await res.json();
    localStorage.setItem(this.keys.AUTH_TOKEN, data.access_token);
    if (data.refresh_token) {
      localStorage.setItem(this.keys.REFRESH_TOKEN, data.refresh_token);
    }

    // Fetch user details
    await this.fetchCurrentUser();
    return data;
  }

  async registerOrganization(payload) {
    const res = await fetch(`${window.APP_CONFIG.API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Registration failed. Slug or email may already be taken.");
    }

    return await res.json();
  }

  async fetchCurrentUser() {
    try {
      const user = await window.apiClient.request("/auth/me");
      localStorage.setItem(this.keys.USER_PROFILE, JSON.stringify(user));
      return user;
    } catch (e) {
      console.warn("Failed to fetch current user profile:", e);
      return null;
    }
  }

  logout() {
    localStorage.removeItem(this.keys.AUTH_TOKEN);
    localStorage.removeItem(this.keys.REFRESH_TOKEN);
    localStorage.removeItem(this.keys.USER_PROFILE);
    localStorage.removeItem(this.keys.TENANT_CONTEXT);
    window.location.href = "index.html";
  }

  impersonateTenant(tenantSlug, token) {
    localStorage.setItem(this.keys.AUTH_TOKEN, token);
    localStorage.setItem(this.keys.TENANT_CONTEXT, tenantSlug);
    window.location.href = "portal.html";
  }

  requirePortalAuth() {
    if (!this.isAuthenticated()) {
      window.location.href = "index.html?auth=login&redirect=portal.html";
      return false;
    }
    return true;
  }

  requireStaffAuth() {
    if (!this.isAuthenticated()) {
      window.location.href = "index.html?auth=staff&redirect=staff.html";
      return false;
    }
    const user = this.getUser();
    if (user && user.role !== "SUPER_ADMIN" && user.role !== "SUPPORT_AGENT" && user.role !== "BILLING_ADMIN") {
      alert("Access Denied: You do not have Superadmin or Staff backoffice privileges.");
      window.location.href = "portal.html";
      return false;
    }
    return true;
  }
}

window.authService = new AuthService();
