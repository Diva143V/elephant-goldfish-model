# CLI Automation & DevTools Protocol Guide

This guide specifies how EGM agents actuate Google Chrome and integrate with the Chrome DevTools Protocol (CDP) or `chrome-devtools` CLI.

---

## 1. Browser Lifecycle Management

Browser instances are launched and supervised using the cross-platform platform bridge [`scripts/launch_browser.py`](../../../scripts/launch_browser.py).

### Launching Headless (Default)
```bash
python scripts/launch_browser.py --url "http://localhost:3000" --mode headless --json
```

### Launching Visible GUI Mode
```bash
python scripts/launch_browser.py --url "http://localhost:3000" --mode visible --json
```

### Checking Status & Stopping Sessions
```bash
python scripts/launch_browser.py --status
python scripts/launch_browser.py --stop
```

The launcher automatically:
1. Locates Chrome on Windows, macOS, or Linux.
2. Directs Chrome to bind an available ephemeral port using `--remote-debugging-port=0`.
3. Reads the assigned port from `DevToolsActivePort`.
4. Writes session metadata to `.egm/browser-sessions.json`.
5. Cleans up temporary profiles upon session termination.

---

## 2. DevTools Client Attachment

Once Chrome is running, tools attach via the local debugging URL returned by the launcher:

```bash
chrome-devtools start --browserUrl=http://127.0.0.1:<PORT>
```

### Essential Navigation & Inspection Commands
* **Navigate to URL**:
  ```bash
  chrome-devtools navigate_page 1 --url "http://localhost:3000"
  ```
* **Capture Pruned Accessibility Snapshot**:
  ```bash
  chrome-devtools take_snapshot 1
  ```
* **Capture Viewport Screenshot**:
  ```bash
  chrome-devtools take_screenshot 1 --filePath "screenshot.png"
  ```
* **Evaluate Read-Only DOM Expression**:
  ```bash
  chrome-devtools evaluate_script "document.title" --pageId 1
  ```

---

## 3. Pruned DOM Extraction Protocol

To avoid saturating the LLM context window (capping payloads at <= 2,000 tokens):
1. **Target Landmarks**: Inspect specific semantic containers (`main`, `nav`, `header`, `footer`) rather than dumping `<html>`.
2. **Interactive Elements Only**: Filter for actionable controls (`a[href]`, `button`, `input`, `select`, `textarea`).
3. **Strip Ephemeral Attributes**: Omit inline styles, SVG paths, base64 data URIs, and deep layout wrappers.

---

## 4. Artifact-First Delivery Standard

Raw HTML dumps and terminal logs must never be printed directly in chat. All inspection outputs must be written directly to `browser_inspection_report.md`:

```markdown
# Browser Inspection Report: [Page Title]

* **URL:** `[TargetURL]`
* **Timestamp:** [ISO-8601]
* **Display Mode:** [Headless | Visible]
* **HTTP Status:** [200 | 404 | 500]

## Visual Screenshot
![Viewport Screenshot](screenshot.png)

## Interactive Element Landmark Outline
* `button#submit`: "Sign In" (Enabled)
* `input#email`: "Email address" (Empty)
* `a.nav-link`: "Documentation" (href="/docs")

## Console Diagnostics
* No uncaught JavaScript exceptions detected.
```

