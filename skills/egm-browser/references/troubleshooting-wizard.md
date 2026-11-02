# Browser Troubleshooting Wizard & Diagnostics

This reference guides resolution for common browser actuation failures, handshake timeouts, and platform-specific quirks.

---

## 1. Handshake Failures (`DevToolsActivePort` Missing)

### Symptom
`Timed out waiting for DevToolsActivePort in <path>` or `Could not find DevToolsActivePort`.

### Causes & Remediations
1. **Chrome Binary Missing or Incompatible**:
   - Verify that Google Chrome, Chromium, or Microsoft Edge is installed on the host.
   - Run `python scripts/launch_browser.py --status` to check binary discovery.
2. **Profile Lock Conflict**:
   - A previously orphaned Chrome instance may hold a lock on the temporary profile directory.
   - Run `python scripts/launch_browser.py --stop` to terminate lingering processes.
3. **Headless Linux Missing Dependencies**:
   - On Linux systems without GUI libraries, ensure essential shared libraries (`libnss3`, `libatk1.0-0`, `libcups2`) are installed, or install Chromium via package manager.

---

## 2. Windows Session Isolation & Hidden Windows

### Symptom
Browser launches in visible mode (`--visible`), but no browser window appears on the desktop monitor.

### Cause
Subprocesses spawned by certain background runner shells (e.g., processes with `windowsHide: true` or running in Session 0) cannot render windows into the interactive desktop station (`winsta0\default`).

### Remediation
[`scripts/launch_browser.py`](../../../scripts/launch_browser.py) automatically handles this by launching detached processes into the interactive session. If manual intervention is required, launch Chrome using the host Windows Shell:
```powershell
Start-Process "chrome.exe" -ArgumentList "--remote-debugging-port=0","--user-data-dir=$env:TEMP\egm-browser-profile","http://localhost:3000"
```

---

## 3. Error Classification Matrix

To distinguish harness crashes from application bugs:

| Error Domain | Typical Symptoms | Remediation Path |
| :--- | :--- | :--- |
| **`INFRASTRUCTURE_FAILURE`** | Port bind refused, Chrome crashed on startup, socket disconnected mid-call. | Automatic single retry with a fresh ephemeral port and profile directory. |
| **`TARGET_APP_FAILURE`** | Web server returned HTTP 500, network connection refused at target port, unhandled JS error. | Do not retry. Report application failure in the inspection artifact. |
| **`TIMEOUT_BREACH`** | Page took longer than 30s to fire `networkidle` or `DOMContentLoaded`. | Degrade to static screenshot capture; note slow loading in report. |

---

## 4. Emergency Cleanup & Stale Process Reaping

If Chrome instances remain running after an unexpected session termination:

```bash
# Terminate all active EGM browser sessions and remove profiles
python scripts/launch_browser.py --stop
```

On Windows, you can forcefully kill lingering processes if needed:
```powershell
Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*egm-browser*" } | Stop-Process -Force
```

