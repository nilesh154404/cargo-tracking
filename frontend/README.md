# Standalone Enterprise Multi-Tenant Cargo Tracking Frontend

This directory contains the completely decoupled, standalone frontend application for the Cargo Intelligence Platform, featuring:
1. **Public Marketing Website & Live Quick-Tracker Sandbox** (`index.html`)
2. **Multi-Tenant Customer Portal** (`portal.html`)
3. **Superadmin & Staff Backoffice Cockpit** (`staff.html`)

---

## 1. Quick Start

### Option A: Using NPM (Recommended)
From the `frontend/` directory:
```bash
npm start
# Opens at http://localhost:3000
```

### Option B: Using Python HTTP Server
```bash
python3 -m http.server 3000
# Opens at http://localhost:3000
```

---

## 2. Architecture & File Structure

```
frontend/
├── index.html           # Public Marketing Website & Live Cargo Sandbox
├── portal.html          # Multi-Tenant Customer Operations Portal (/app)
├── staff.html           # Superadmin & Internal Staff Operations Backoffice (/staff)
├── css/
│   ├── theme.css        # Universal design system tokens, typography, dark glassmorphism
│   ├── website.css      # Marketing site, hero, live tracker, journey bar, pricing
│   ├── portal.css       # Customer portal, sidebar navigation, quota bar, batch dropzone
│   └── staff.css        # Superadmin cockpit, carrier health grid, cURL debugger
├── js/
│   ├── config.js        # API Base URL configuration (default: http://localhost:8000/api/v1)
│   ├── api.js           # Decoupled HTTP Client with Bearer tokens & X-API-Key injection
│   ├── auth.js          # Authentication, registration, session storage, and RBAC guards
│   ├── website.js       # Live tracking sandbox, code tabs, pricing slider, auth modals
│   ├── portal.js        # Tenant dashboard, descending timeline, batch CSV runner, API keys
│   └── staff.js         # Superadmin KPIs, tenant manager, quota adjuster, carrier SLA
└── package.json         # Standalone scripts and dev server
```

---

## 3. Connecting to the Backend Service

By default, `frontend/js/config.js` directs API requests to:
```javascript
window.APP_CONFIG.API_BASE_URL = "http://localhost:8000/api/v1";
```

Ensure the backend service in `/shipment-tracking` is running:
```bash
cd ../shipment-tracking
venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
