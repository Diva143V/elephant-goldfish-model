#!/usr/bin/env python3
# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0

"""Cross-platform launcher bridge for Chrome DevTools browser actuation in EGM.

Discovers Chrome binaries, binds ephemeral remote debugging ports, manages
session lifecycles, and supervises child processes to prevent zombies.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

SESSION_REGISTRY_FILE = Path(".egm/browser-sessions.json")


def find_chrome_executable() -> Optional[str]:
  """Locate Google Chrome or Chromium executable on the host system."""
  system = sys.platform

  if system == "win32":
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))
        / "Microsoft/Edge/Application/msedge.exe",
    ]
    for candidate in candidates:
      if candidate.is_file():
        return str(candidate.resolve())
    for name in ("chrome.exe", "chrome", "msedge.exe"):
      found = shutil.which(name)
      if found:
        return found

  elif system == "darwin":
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    for candidate in candidates:
      if candidate.is_file():
        return str(candidate.resolve())
    for name in ("google-chrome", "chromium"):
      found = shutil.which(name)
      if found:
        return found

  else:  # Linux / Unix
    for name in (
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
    ):
      found = shutil.which(name)
      if found:
        return found

  return None


def parse_devtools_active_port(content: str) -> Optional[Tuple[int, str]]:
  """Parse port and WebSocket target path from DevToolsActivePort file content."""
  lines = [line.strip() for line in content.splitlines() if line.strip()]
  if len(lines) >= 2:
    try:
      port = int(lines[0])
      ws_path = lines[1]
      return port, ws_path
    except ValueError:
      return None
  return None


def poll_devtools_active_port(
    profile_dir: Path, timeout: float = 10.0
) -> Optional[Tuple[int, str]]:
  """Poll user data directory until DevToolsActivePort file is written and valid."""
  port_file = profile_dir / "DevToolsActivePort"
  deadline = time.time() + timeout
  while time.time() < deadline:
    if port_file.is_file():
      try:
        content = port_file.read_text(encoding="utf-8")
        parsed = parse_devtools_active_port(content)
        if parsed is not None:
          return parsed
      except (OSError, UnicodeDecodeError):
        pass
    time.sleep(0.1)
  return None


def assign_windows_job_object(process_handle: int) -> bool:
  """Assign process handle to a Windows Job Object with KILL_ON_JOB_CLOSE."""
  if sys.platform != "win32":
    return False
  try:
    kernel32 = ctypes.windll.kernel32
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
      return False

    # JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    # LimitFlags offset is at 16 bytes (following basic limit information)
    class IO_COUNTERS(ctypes.Structure):
      _fields_ = [
          ("ReadOperationCount", ctypes.c_uint64),
          ("WriteOperationCount", ctypes.c_uint64),
          ("OtherOperationCount", ctypes.c_uint64),
          ("ReadTransferCount", ctypes.c_uint64),
          ("WriteTransferCount", ctypes.c_uint64),
          ("OtherTransferCount", ctypes.c_uint64),
      ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
      _fields_ = [
          ("PerProcessUserTimeLimit", ctypes.c_int64),
          ("PerJobUserTimeLimit", ctypes.c_int64),
          ("LimitFlags", ctypes.c_uint32),
          ("MinimumWorkingSetSize", ctypes.c_size_t),
          ("MaximumWorkingSetSize", ctypes.c_size_t),
          ("ActiveProcessLimit", ctypes.c_uint32),
          ("Affinity", ctypes.c_size_t),
          ("PriorityClass", ctypes.c_uint32),
          ("SchedulingClass", ctypes.c_uint32),
      ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
      _fields_ = [
          ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
          ("IoInfo", IO_COUNTERS),
          ("ProcessMemoryLimit", ctypes.c_size_t),
          ("JobMemoryLimit", ctypes.c_size_t),
          ("PeakProcessMemoryLimit", ctypes.c_size_t),
          ("PeakJobMemoryLimit", ctypes.c_size_t),
      ]

    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

    JobObjectExtendedLimitInformation = 9
    success = kernel32.SetInformationJobObject(
        job,
        JobObjectExtendedLimitInformation,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not success:
      return False

    return bool(kernel32.AssignProcessToJobObject(job, process_handle))
  except Exception:
    return False


def load_registry() -> Dict[str, Any]:
  """Load active browser session registry from disk."""
  if SESSION_REGISTRY_FILE.is_file():
    try:
      return json.loads(SESSION_REGISTRY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
      return {"sessions": []}
  return {"sessions": []}


def save_registry(registry: Dict[str, Any]) -> None:
  """Persist browser session registry to disk."""
  SESSION_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
  SESSION_REGISTRY_FILE.write_text(
      json.dumps(registry, indent=2), encoding="utf-8"
  )


def record_session(session: Dict[str, Any]) -> None:
  """Add an active session to the registry."""
  registry = load_registry()
  sessions = [s for s in registry.get("sessions", []) if s.get("pid") != session.get("pid")]
  sessions.append(session)
  registry["sessions"] = sessions
  save_registry(registry)


def remove_session(pid: int) -> None:
  """Remove a terminated session from the registry."""
  registry = load_registry()
  sessions = [s for s in registry.get("sessions", []) if s.get("pid") != pid]
  registry["sessions"] = sessions
  save_registry(registry)


def is_process_running(pid: int) -> bool:
  """Check if a process PID is currently active."""
  if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
      return False
    exit_code = ctypes.c_ulong()
    STILL_ACTIVE = 259
    success = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    kernel32.CloseHandle(handle)
    return bool(success and exit_code.value == STILL_ACTIVE)
  else:
    try:
      os.kill(pid, 0)
      return True
    except (OSError, ProcessLookupError):
      return False


def terminate_pid(pid: int) -> bool:
  """Terminate a process by PID cleanly."""
  if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
    PROCESS_TERMINATE = 0x0001
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if handle:
      result = kernel32.TerminateProcess(handle, 1)
      kernel32.CloseHandle(handle)
      return bool(result)
    return False
  else:
    try:
      os.kill(pid, signal.SIGTERM)
      time.sleep(0.2)
      if is_process_running(pid):
        os.kill(pid, signal.SIGKILL)
      return True
    except (OSError, ProcessLookupError):
      return False


def stop_sessions(all_sessions: bool = True) -> int:
  """Stop active sessions and clean up temporary profiles."""
  registry = load_registry()
  sessions = registry.get("sessions", [])
  stopped = 0

  for s in sessions:
    pid = s.get("pid")
    profile = s.get("profile_dir")
    if pid and is_process_running(pid):
      terminate_pid(pid)
      stopped += 1
    if profile:
      try:
        shutil.rmtree(profile, ignore_errors=True)
      except Exception:
        pass

  save_registry({"sessions": []})
  return stopped


def launch_browser(
    url: str = "about:blank",
    mode: str = "headless",
    profile_dir: Optional[str] = None,
) -> Dict[str, Any]:
  """Launch Chrome, bind ephemeral remote debugging port, and return session info."""
  chrome_bin = find_chrome_executable()
  if not chrome_bin:
    raise FileNotFoundError(
        "Google Chrome or Chromium executable not found on host system."
    )

  if not profile_dir:
    profile_dir = tempfile.mkdtemp(prefix="egm-browser-profile-")
  profile_path = Path(profile_dir).resolve()
  profile_path.mkdir(parents=True, exist_ok=True)

  cmd = [
      chrome_bin,
      "--remote-debugging-port=0",
      f"--user-data-dir={profile_path}",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-background-networking",
      "--disable-sync",
  ]

  if mode == "headless":
    cmd.append("--headless=new")
  else:
    # Visible mode: verify display if on Linux
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
      cmd.append("--headless=new")
      mode = "headless (fallback: missing DISPLAY)"

  cmd.append(url)

  # Spawn child process
  if sys.platform == "win32":
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW = 0x08000000
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    if mode.startswith("headless"):
      flags |= CREATE_NO_WINDOW
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
    )
  else:
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setpgrp,
        close_fds=True,
    )

  # Poll for DevToolsActivePort
  parsed = poll_devtools_active_port(profile_path, timeout=10.0)
  if not parsed:
    proc.terminate()
    shutil.rmtree(profile_path, ignore_errors=True)
    raise TimeoutError(
        f"Timed out waiting for DevToolsActivePort in {profile_path}"
    )

  port, ws_path = parsed
  session_info = {
      "pid": proc.pid,
      "port": port,
      "ws_url": f"ws://127.0.0.1:{port}{ws_path}",
      "browser_url": f"http://127.0.0.1:{port}",
      "profile_dir": str(profile_path),
      "mode": mode,
      "url": url,
      "started_at": time.time(),
  }

  record_session(session_info)
  return session_info, proc


def main() -> int:
  parser = argparse.ArgumentParser(
      description="EGM Cross-Platform Browser Launcher Bridge"
  )
  parser.add_argument(
      "--url", default="about:blank", help="Target URL to navigate"
  )
  parser.add_argument(
      "--mode",
      choices=["headless", "visible"],
      default="headless",
      help="Display mode (default: headless)",
  )
  parser.add_argument(
      "--status", action="store_true", help="Print active browser sessions"
  )
  parser.add_argument(
      "--stop", action="store_true", help="Stop running browser sessions"
  )
  parser.add_argument(
      "--keep-alive",
      action="store_true",
      help="Keep launcher running in foreground to maintain browser lifecycle",
  )
  parser.add_argument(
      "--json", action="store_true", help="Output results in JSON format"
  )

  args = parser.parse_args()

  if args.stop:
    stopped = stop_sessions(all_sessions=True)
    if args.json:
      print(json.dumps({"status": "stopped", "count": stopped}))
    else:
      print(f"Stopped {stopped} browser session(s).")
    return 0

  if args.status:
    registry = load_registry()
    sessions = registry.get("sessions", [])
    active = [s for s in sessions if is_process_running(s.get("pid", 0))]
    if args.json:
      print(json.dumps({"active_sessions": active}, indent=2))
    else:
      print(f"Active browser sessions: {len(active)}")
      for s in active:
        print(f"  PID: {s.get('pid')}, Port: {s.get('port')}, Mode: {s.get('mode')}, URL: {s.get('url')}")
    return 0

  try:
    session, proc = launch_browser(url=args.url, mode=args.mode)
    if args.json:
      print(json.dumps(session, indent=2))
    else:
      print(f"Browser launched (PID {session['pid']})")
      print(f"  Mode: {session['mode']}")
      print(f"  Remote debugging URL: {session['browser_url']}")
      print(f"  WebSocket URL: {session['ws_url']}")
      print(f"  Profile directory: {session['profile_dir']}")

    if args.keep_alive and proc:
      try:
        proc.wait()
      except KeyboardInterrupt:
        proc.terminate()
        stop_sessions(all_sessions=True)
    return 0
  except Exception as e:
    if args.json:
      print(json.dumps({"error": str(e)}, indent=2))
    else:
      print(f"Error: {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
  sys.exit(main())
