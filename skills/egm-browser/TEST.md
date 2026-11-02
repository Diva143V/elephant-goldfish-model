# Verification Playbook: `egm-browser`

This checklist details manual and automated verification procedures for the `egm-browser` skill.

---

## 1. Automated Unit Tests

Execute the unit test suite verifying frontmatter, packaging integration, link integrity, and launcher mechanics:

```bash
pytest tests/unit/test_browser_skill.py -v
pytest tests/unit/test_frontmatter.py -v
pytest tests/unit/test_scenario_coverage.py -v
pytest tests/unit/test_skill_load_limits.py -v
```

---

## 2. Interactive Launcher & Port Allocation Tests

1. **Verify Headless Execution**:
   ```bash
   python scripts/launch_browser.py --url "about:blank" --mode headless --json
   ```
   *Expected Result*: Returns JSON with `pid`, `port`, `ws_url`, and `browser_url`.

2. **Verify Ephemeral Port Parsing**:
   Inspect the temporary user data directory referenced in the output and confirm that `DevToolsActivePort` was parsed correctly.

3. **Verify Session Cleanup**:
   ```bash
   python scripts/launch_browser.py --stop
   python scripts/launch_browser.py --status
   ```
   *Expected Result*: Reports 0 active browser sessions and temporary profile directories are cleaned up.

---

## 3. URL Security Guardrail Verification

* **Allowlist Acceptance**:
  - `http://localhost:3000` -> Permitted autonomously.
  - `http://127.0.0.1:8080` -> Permitted autonomously.
* **Denylist Rejection**:
  - `chrome://settings` -> Strictly blocked with `SECURITY_VIOLATION`.
  - `http://169.254.169.254/latest/meta-data/` -> Strictly blocked with `SECURITY_VIOLATION`.
  - `file:///C:/Windows/System32` -> Strictly blocked with `SECURITY_VIOLATION`.

