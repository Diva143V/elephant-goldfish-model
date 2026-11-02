# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the egm-browser skill and cross-platform launcher bridge."""

from pathlib import Path
import re
import runpy
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills/egm-browser"
DIST_DIR = ROOT / "distributions/claude/skills/egm-browser"
launcher = runpy.run_path(str(ROOT / "scripts/launch_browser.py"))


def test_browser_skill_reference_parity() -> None:
  """All references must exist and be identical across root and distributions."""
  source_refs = {
      p.relative_to(SKILL_DIR): p.read_bytes()
      for p in (SKILL_DIR / "references").glob("*.md")
  }
  assert source_refs, "No references found in skills/egm-browser/references"

  dist_refs = {
      p.relative_to(DIST_DIR): p.read_bytes()
      for p in (DIST_DIR / "references").glob("*.md")
  }
  assert source_refs == dist_refs, (
      "Reference files in distributions/claude differ from skills/egm-browser"
  )


def test_browser_skill_relative_links_resolve() -> None:
  """Relative markdown links in SKILL.md and references must resolve on disk."""
  for doc in [SKILL_DIR / "SKILL.md"] + list((SKILL_DIR / "references").glob("*.md")):
    content = doc.read_text(encoding="utf-8")
    clean = re.sub(r"```[\s\S]*?```", "", content)
    clean = re.sub(r"`[^`]*`", "", clean)
    links = re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]*)?\)", clean)
    for link in links:
      if link.startswith(("http://", "https://", "mailto:", "file://")):
        continue
      if link.startswith(("#", "$", "{", "<")):
        continue
      resolved = (doc.parent / link).resolve()
      assert resolved.exists(), f"{doc}: broken relative link '{link}'"


def test_parse_devtools_active_port_valid() -> None:
  """DevToolsActivePort content with port and path parses correctly."""
  sample = "9342\n/devtools/browser/7b134d10-e7f1-43e8-8a8f-89a19c629235\n"
  parsed = launcher["parse_devtools_active_port"](sample)
  assert parsed == (9342, "/devtools/browser/7b134d10-e7f1-43e8-8a8f-89a19c629235")


def test_parse_devtools_active_port_invalid() -> None:
  """Malformed DevToolsActivePort returns None."""
  assert launcher["parse_devtools_active_port"]("") is None
  assert launcher["parse_devtools_active_port"]("not_a_number\n/path\n") is None
  assert launcher["parse_devtools_active_port"]("9342\n") is None


def test_find_chrome_executable() -> None:
  """find_chrome_executable locates a valid binary if present on host."""
  exe = launcher["find_chrome_executable"]()
  if exe is not None:
    path = Path(exe)
    assert path.is_file(), f"Discovered Chrome path is not a file: {exe}"


def test_session_registry_empty_or_valid() -> None:
  """Session registry loading returns a valid dictionary structure."""
  registry = launcher["load_registry"]()
  assert isinstance(registry, dict)
  assert "sessions" in registry
  assert isinstance(registry["sessions"], list)


def test_is_process_running_invalid_pid() -> None:
  """Invalid or negative PID returns False."""
  assert launcher["is_process_running"](0) is False
  assert launcher["is_process_running"](-1) is False
