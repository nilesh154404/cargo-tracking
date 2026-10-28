/**
 * Global Configuration for Decoupled Frontend
 * Directs all REST calls to the backend API service (default: http://localhost:8000/api/v1)
 */
window.APP_CONFIG = {
  API_BASE_URL: window.API_BASE_URL || "http://localhost:8000/api/v1",
  DEMO_API_KEY: "cargotrk_live_defaultdemo00000000000000000",
  STORAGE_KEYS: {
    AUTH_TOKEN: "cargotrk_auth_token",
    REFRESH_TOKEN: "cargotrk_refresh_token",
    USER_PROFILE: "cargotrk_user_profile",
    TENANT_CONTEXT: "cargotrk_tenant_context",
    STAFF_TOKEN: "cargotrk_staff_token",
  },
  DEFAULT_SAMPLE_TRACKS: [
    { number: "MSMU6484830", mode: "SEA", carrier: "MSC (Mediterranean Shipping Co)" },
    { number: "MEDU9650838", mode: "SEA", carrier: "MSC (Mediterranean Shipping Co)" },
    { number: "160-15246221", mode: "AIR", carrier: "Cathay Pacific Cargo" },
    { number: "MAEU1234567", mode: "SEA", carrier: "Maersk Line" }
  ]
};
