"""Choose a supported JavaScript runtime for yt-dlp.

Deno >=2.3 is the preferred runtime. Node.js is an explicit fallback only
when its release line has the October 21, 2026 security fixes (or newer).
Unknown or end-of-life Node release lines are rejected rather than guessed safe.
See https://nodejs.org/en/blog/vulnerability/october-2026-security-releases
"""
from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any

# Minimum *security-patched* versions for the supported release lines.
# Update this mapping when new Node.js major lines are formally supported.
MINIMUM_PATCHED_NODE: dict[int, tuple[int, int, int]] = {
    22: (22, 23, 4),
    24: (24, 22, 1),
    26: (26, 12, 1),
}
MINIMUM_DENO = (2, 3, 0)
NODE_ADVISORY = "https://nodejs.org/en/blog/vulnerability/october-2026-security-releases"


def _version_output(runtime: str, executable: str) -> tuple[int, int, int] | None:
    """Read a runtime's version without invoking a shell or arbitrary script."""
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True,
            check=False, timeout=4,
        )
        if result.returncode != 0:
            return None
        first = result.stdout.splitlines()[0] if result.stdout else ""
        pattern = r"deno\s+(\d+)\.(\d+)\.(\d+)(?:\s|$)" if runtime == "deno" else r"v(\d+)\.(\d+)\.(\d+)(?:\s|$)"
        match = re.match(pattern, first)
        return tuple(map(int, match.groups())) if match else None
    except (OSError, subprocess.TimeoutExpired, IndexError, ValueError, TypeError):
        return None


def node_version_supported(version: tuple[int, int, int]) -> bool:
    """Reject vulnerable, EOL and unreviewed Node.js releases."""
    minimum = MINIMUM_PATCHED_NODE.get(version[0])
    return minimum is not None and version >= minimum


def runtime_details() -> dict[str, Any]:
    """Report the preferred supported runtime and detected versions for /health."""
    detected: dict[str, str] = {}
    for name in ("deno", "node"):
        executable = shutil.which(name)
        if executable is None:
            continue
        version = _version_output(name, executable)
        detected[name] = ".".join(map(str, version)) if version is not None else "unreadable version"
        supported = (version is not None and
                     ((name == "deno" and version >= MINIMUM_DENO) or
                      (name == "node" and node_version_supported(version))))
        if supported:
            return {"runtime": name, "version": detected[name], "supported": True,
                    "note": "Deno preferred" if name == "deno" else "Node.js security-patched fallback",
                    "detected": detected}
    requirements = ", ".join(f"Node.js {'.'.join(map(str, v))}+ ({major}.x)" for major, v in MINIMUM_PATCHED_NODE.items())
    return {"runtime": None, "version": None, "supported": False,
            "note": f"Install Deno 2.3+ (recommended) or a security-patched Node.js: {requirements}. "
                    f"See {NODE_ADVISORY}",
            "detected": detected}


def yt_dlp_js_options() -> dict[str, Any]:
    """Leave yt-dlp's default Deno selection, otherwise permit only patched Node."""
    chosen = runtime_details()
    if chosen["runtime"] == "node":
        return {"js_runtimes": {"node": {}}}
    return {}