# EGM Browser Skill (`egm-browser`)

* **Author:** @Diva143V
* **Date:** 2026-11-02

## Overview

`egm-browser` is an upstream browser inspection and visual verification skill for the Elephant-Goldfish Model (EGM) framework. It enables EGM agents and users to capture visual screenshots, extract DOM outlines, and verify live web application rendering using the Chrome DevTools MCP protocol. The skill adheres strictly to EGM's Spec-Driven Development (SDD) boundaries: actuation occurs strictly at the Elephant/harness layer, producing static, read-only inspection artifacts that isolated Goldfish reviewers can audit without granting them execution permissions or network access.

---

## Analysis

The 6-lens Goldfish brainstorm review identified critical governance, architectural, and operational constraints across the feature concept:

### 1. Scope Boundary & YAGNI Assessment (Skeptical Architect & Structural)
* **Core Risk**: EGM is a lightweight plugin dedicated to specification drafting and zero-context reviews. Expanding `egm-browser` into an all-in-one APM/QA suite (Lighthouse audits, Core Web Vitals LCP waterfall tracing, V8 heap snapshot diffing, and cookie consent headers) causes severe architectural scope creep and maintenance bloat.
* **Resolution**: Enforce strict scope reduction. Cut specialized performance and memory profiling from the core skill. Focus exclusively on interactive page navigation, visual rendering (screenshots), and structural DOM extraction. Specialized diagnostics belong in dedicated external CLI tools (`lighthouse-ci`, `playwright`, `axe-core`).

### 2. Packaging & Multi-Harness Compatibility (Rollout & Structural)
* **Core Risk**: `scripts/pack_plugin.py` and `tests/unit/test_packaging.py` explicitly forbid declaring `mcpServers` or `mcp` in `plugin.json`. Embedding binary MCP configurations breaks the reproducible packaging engine and violates client validation in non-Antigravity runtimes (Claude Code, Codex, ChatGPT Work).
* **Resolution**: Decouple MCP declarations from the distribution bundle. `egm-browser` must remain a pure markdown instruction set that consumes host-provided MCP tools. If the host lacks browser MCP tools, the skill must provide actionable setup instructions rather than bundling binary daemons.
* **Skill Load Limit**: The body of `skills/egm-browser/SKILL.md` must remain strictly below the 24,000-byte limit enforced by `tests/unit/test_skill_load_limits.py`.

### 3. Read-Only Goldfish Isolation Invariant (Rollout & Compatibility)
* **Core Risk**: Claude Code and EGM review subagents operate under strict read-only constraints (`tools: ["Read", "Grep", "Glob"]`). Granting browser actuation or arbitrary JavaScript evaluation (`Runtime.evaluate`) to Goldfish reviewers violates the core security invariant of zero-side-effect reviews.
* **Resolution**: Asymmetric architecture. Browser actuation is restricted to the interactive orchestrator (Elephant). The Elephant executes navigation and capture, generating static markdown reports (`browser_inspection_report.md`) and compressed images (`screenshot.png`). Goldfish subagents evaluate only the generated static artifacts using their standard `Read` tools.

### 4. Process Supervision & Dynamic Port Allocation (Architecture & Telemetry)
* **Core Risk**: Spawning child Chrome processes causes orphaned zombie processes on agent timeouts, while pre-allocating port 0 suffers from time-of-check to time-of-use (TOCTOU) socket collisions.
* **Resolution**:
  - Launch Chrome with native ephemeral port binding (`--remote-debugging-port=0`) and extract the active port from `DevToolsActivePort` in the temporary profile directory.
  - Manage process lifecycles via Windows Job Objects (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) and POSIX process groups to guarantee child browser termination upon session exit.
  - Maintain a local session registry (`.egm/browser-sessions.json`) to track and reap stale processes.

### 5. Telemetry & Error Categorization (Codebase Details & SRE)
* **Core Risk**: Flat error messages ("Navigation timed out") conflate infrastructure crashes (Chrome failure, port bind refusal) with target application defects (web server 500 error, fatal JS runtime error). This leads to false CI failures and infinite retry loops.
* **Resolution**: Implement a machine-readable error envelope that differentiates `INFRASTRUCTURE_FAILURE` (permitting exactly 1 automatic retry on an alternate port) from `TARGET_APP_FAILURE` (deterministic application defect reported directly in the design audit).

### 6. Ergonomics & Token Budgeting (UX & Design Critic)
* **Core Risk**: Raw accessibility trees and DOM serializations exceed 50,000–100,000 tokens, quickly blowing out model context windows. Forcing users through 3-question intake gates before every command creates high cognitive friction.
* **Resolution**:
  - Adopt zero-configuration defaults: headless execution by default (`--headless=new`), auto-discovering active localhost dev ports.
  - Prune DOM/AX trees to interactive semantic elements (depth <= 4, numerical element IDs, strictly capped at <= 2,000 tokens).
  - Compress screenshots to WebP/JPEG (max 1024x768) stored locally on disk, passing file paths rather than streaming raw base64 payloads into chat context.

---

## Goals vs. Non-Goals

### In-Scope Goals
1. **Interactive Navigation & Inspection**: Provide EGM agents with verified capabilities to navigate to target URLs, wait for network idle, click elements, fill form inputs, and capture DOM state.
2. **Visual Evidence Generation**: Capture resized, compressed viewport screenshots stored directly to disk and linked inside markdown reports.
3. **Cross-Platform Launcher**: Provide a zero-dependency launcher (`scripts/launch_browser.py`) supporting Windows, macOS, and Linux with dynamic ephemeral port binding (`--remote-debugging-port=0`).
4. **Asymmetric Artifact Workflow**: Generate static inspection artifacts (`browser_inspection_report.md`) for read-only consumption by downstream EGM skills (`egm-review`, `egm-draft`).
5. **Robust Error Diagnostics**: Provide structured error categorization (`INFRASTRUCTURE_FAILURE` vs. `TARGET_APP_FAILURE`) with actionable troubleshooting output.

### Out-of-Scope Non-Goals
1. **Deep Performance & Memory Diagnostics**: No in-tree Lighthouse engine, V8 heap snapshot diffing, or Core Web Vitals waterfall tracing. Specialized profiling belongs in dedicated CLI tools.
2. **Bundled MCP Servers**: EGM will not ship or bundle binary Chrome DevTools MCP servers in `plugin.json` or runtime distributions.
3. **Autonomous End-to-End Test Automation**: The skill is an inspection and spec-verification tool, not a replacement for Playwright/Cypress end-to-end test runners.
4. **Actuation Inside Goldfish Subagents**: Review personas (`agents/*.md`) will never be granted browser execution tools; Goldfish remain strictly read-only.
5. **Bypassing CAPTCHAs & Bot Detection**: No evasion mechanisms, fingerprint spoofing, or automated CAPTCHA solving.

---

## Alternatives Weighed

1. **Monolithic Multi-Tier QA Suite (Rejected)**:
   * *Proposal*: Bundle accessibility audits, performance tracing, memory leak diffing, and cookie security audits into `egm-browser`.
   * *Rejection Rationale*: Violates YAGNI and expands EGM's scope from specification design into runtime APM. Exceeds the 24,000-byte `SKILL.md` load limit and creates heavy maintenance debt.
2. **In-Tree MCP Server Packaging (Rejected)**:
   * *Proposal*: Bundle and configure `chrome-devtools-mcp` directly inside `plugin.json`.
   * *Rejection Rationale*: Strictly forbidden by `pack_plugin.py` and `test_refuses_unbundled_services`. Breaks portable packaging and multi-harness distribution across Claude Code and Codex.
3. **Direct Port Pre-Reservation (Rejected)**:
   * *Proposal*: Allocate a port using temporary socket binding (e.g. probing port 9222/9333) and pass `--remote-debugging-port=<port>`.
   * *Rejection Rationale*: Subject to TOCTOU race conditions under parallel execution. Replaced with native Chrome ephemeral port binding (`--remote-debugging-port=0`) and `DevToolsActivePort` reading.
4. **Proprietary Carousel Formatting (Rejected)**:
   * *Proposal*: Use Antigravity ````carousel` blocks to render multi-slide inspection views.
   * *Rejection Rationale*: Breaks in non-Antigravity runtimes (Claude Code CLI, Codex). Replaced with standard GitHub Flavored Markdown (GFM) as the baseline.

---

## Key Decisions & Staging for Next Steps

### Key Decisions
1. **Decoupled Architecture**: EGM provides the skill definition and platform launcher; the host environment provides the Chrome DevTools MCP capability.
2. **Strict Read-Only Review Boundary**: Goldfish reviewers consume pre-rendered visual/DOM markdown artifacts only.
3. **Ephemeral Lifecycle Management**: Zero persistent background processes; Windows Job Objects and process groups ensure complete teardown on session exit.
4. **Two-Stage Governance Track**: In accordance with `AGENTS.md`, progress follows Stage 1 (Design Doc PR) -> Stage 2 (Implementation PR).

### Staging for Next Steps
1. **Stage 1 (Design Specification)**:
   - Advance this brief into formal EGM design document `docs/designs/browser.md`.
   - Update `docs/designs/README.md`.
   - Run `/egm-review docs/designs/browser.md` and verify link integrity.
   - Submit Stage 1 Design Doc PR (`Refs #270`).
2. **Stage 2 (Implementation)**:
   - Implement `skills/egm-browser/SKILL.md` and reference documentation.
   - Implement `scripts/launch_browser.py` with `DevToolsActivePort` parsing and process supervision.
   - Register skill in `scripts/pack_plugin.py` (`SKILLS`, `REQUIRED_SHARED`) and sync across distributions.
   - Add unit test suite `tests/unit/test_browser_skill.py`.

