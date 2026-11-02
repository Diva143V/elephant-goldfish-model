# URL Security Gating & Boundary Protocol

This document defines the two-layer security model governing target navigation and browser automation in `egm-browser`.

---

## 1. Absolute Denylist (Immediate Rejection)

Navigation to the following targets is strictly prohibited and must be blocked before any browser process or network request is initiated:

* **Internal Browser Schemes**:
  - `chrome://*`
  - `chrome-extension://*`
  - `about:*` (except `about:blank` for initial initialization)
  - `edge://*`
* **Local Filesystem Schemes**:
  - `file://*` (file access must use standard file-reading tools, never browser automation).
* **Cloud & Infrastructure Metadata Endpoints**:
  - `http://169.254.169.254/*` (AWS/GCP/Azure instance metadata)
  - `http://metadata.google.internal/*`
  - `http://100.100.100.200/*` (Alibaba Cloud metadata)
* **Non-HTTP Schemes**:
  - `javascript:*`
  - `data:*`
  - `blob:*`

---

## 2. Default Allowlist (Autonomous Execution)

Autonomous navigation and inspection are permitted without confirmation for:

* **Local Development & Preview Servers**:
  - `http://localhost:*`
  - `http://127.0.0.1:*`
  - `http://[::1]:*`
* **Standard Framework Documentation**:
  - Official framework and language documentation domains (e.g. `*.developer.mozilla.org`, `*.python.org`, `*.astronomy.build`, `*.github.io`).

---

## 3. Human Confirmation Gate (External Web Targets)

Any external web address not present in the default allowlist requires explicit human confirmation in chat before navigation is performed:

* **Prompt Format**:
  > Target URL `[URL]` is an external web destination. Proceed with navigation? (y/n)
* **State-Mutating Actions**:
  - Submitting forms, clicking buttons that execute POST/PUT/DELETE, or triggering file downloads requires explicit confirmation in chat regardless of whether the URL is on the allowlist.

