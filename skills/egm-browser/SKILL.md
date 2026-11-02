---
name: egm-browser
license: Apache-2.0
disable-model-invocation: true
description: >-
  Browser actuation and web inspection skill for the Elephant & Goldfish
  Model (EGM). Navigates local preview servers and documentation sites, captures
  visual screenshots, and generates structured inspection artifacts using
  Chrome DevTools protocol with ephemeral port allocation.
---

# EGM Browser: Web Inspection & Visual Verification Protocol

When running in Codex or ChatGPT Work, first read [Codex integration](../../docs/codex.md).
In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

## Overview

This skill provides the Elephant-Goldfish Model (EGM) with autonomous, cross-platform browser actuation and visual verification. It enables agents to inspect running local development servers, navigate documentation, capture visual viewport screenshots, and extract semantic DOM landmarks.

In accordance with EGM's core architectural invariants:
1. **Asymmetric Actuation**: Browser actuation is strictly an upstream, Elephant-level capability. The Elephant launches the browser, navigates to the target page, captures screenshots, and writes a static inspection artifact ([`browser_inspection_report.md`](#artifact-first-delivery)).
2. **Read-Only Goldfish Boundary**: Zero-context Goldfish reviewers ([`web_critic`](../../agents/web_critic.md)) remain strictly read-only (`tools: ["Read", "Grep", "Glob"]`). Reviewers evaluate only the pre-rendered static artifacts using standard file tools, never executing live browser commands or network calls.

---

## Execution Constraints (CRITICAL)

1. **Artifact-First Delivery (MANDATORY)**: You are **STRICTLY FORBIDDEN** from dumping raw HTML, full accessibility trees, or base64 image data into the chat pane. All visual captures and DOM summaries **MUST** be written directly to `browser_inspection_report.md` on disk, surfacing only concise findings and artifact links in chat.
2. **URL Security Gating**: Every navigation target **MUST** pass the two-layer security model defined in [URL Security Protocol](references/url-security.md). Loopback addresses (`localhost`, `127.0.0.1`) are permitted autonomously. Sensitive internal protocols (`chrome://`, `file://`) and metadata endpoints (`169.254.169.254`) are **STRICTLY PROHIBITED**.
3. **Ephemeral Port Allocation**: Browser instances must never bind to hardcoded ports. Use native ephemeral port binding (`--remote-debugging-port=0`) managed via [`scripts/launch_browser.py`](../../scripts/launch_browser.py) to prevent port collisions.
4. **Token Ceiling**: Extracted DOM outlines must filter for semantic, interactive elements only (depth <= 4) and remain strictly capped at <= 2,000 tokens per inspection.
5. **Deterministic Cleanup**: All browser sessions must be terminated upon task completion or failure by executing `python scripts/launch_browser.py --stop`.

---

## Execution Workflow

### Step 1: Intake & Security Gating

1. **Resolve Target URL**:
   - If the user provides a specific URL (e.g. `http://localhost:3000`), validate it against the [URL Security Protocol](references/url-security.md).
   - If no URL is provided, automatically probe for active local dev servers (e.g. Astro on 3000, Vite on 5173, Next.js on 3000). If ambiguous, ask the user directly in chat.
2. **Resolve Display Mode**:
   - Default to **Headless Mode** (`--mode headless`) for fast, non-intrusive inspection.
   - Use **Visible Mode** (`--mode visible`) only when the user explicitly requests to see the rendered browser window on their physical monitor.

### Step 2: Browser Actuation & Capture

1. **Launch Browser Instance**:
   Execute the cross-platform platform bridge:
   ```bash
   python scripts/launch_browser.py --url "<TargetURL>" --mode <headless|visible> --json
   ```
   Capture the assigned `port` and `browser_url` from the JSON response.

2. **Connect DevTools Client & Inspect**:
   Using your harness's DevTools MCP tools or standard CLI (see [CLI Automation Guide](references/cli-automation.md)):
   * Navigate to target route: `navigate_page 1 --url "<TargetURL>"`
   * Capture viewport screenshot: `take_screenshot 1 --filePath "screenshot.png"`
   * Extract pruned semantic DOM: Filter interactive elements (`button`, `input`, `a[href]`) from landmarks (`main`, `nav`).

3. **Handle Errors**:
   If a failure occurs, categorize it according to the [Troubleshooting Wizard](references/troubleshooting-wizard.md):
   * `INFRASTRUCTURE_FAILURE`: Attempt exactly 1 retry using a fresh ephemeral port.
   * `TARGET_APP_FAILURE`: Report application error (e.g. HTTP 500 or uncaught JS) directly in the report without retry.

### Step 3: Artifact Generation & Teardown

1. **Write Inspection Artifact**:
   Write the consolidated findings directly to `browser_inspection_report.md` in the working directory (or artifact directory). Format according to the template in [CLI Automation Guide](references/cli-automation.md).
2. **Terminate Session**:
   Clean up temporary user profiles and browser processes:
   ```bash
   python scripts/launch_browser.py --stop
   ```
3. **Notify User**:
   Provide a concise summary in chat containing:
   * Target URL and HTTP status.
   * Clean markdown link to `browser_inspection_report.md`.
   * Key interactive elements or layout observations.

---

## Downstream Review Integration (`/egm-review`)

When auditing web application interfaces during specification review:
1. The Elephant executes Steps 1–3 above, producing `browser_inspection_report.md` and `screenshot.png`.
2. The review orchestrator invokes the specialized [`web_critic`](../../agents/web_critic.md) persona.
3. The `web_critic` subagent reads the generated report using standard file tools (`Read`) and asserts compliance against the design specification rubric.

