---
name: preflight-check
description: Cheap read-only environment check. Verifies Python >=3.10, the fairscape-cli binary on PATH, and the three Python packages the wizard imports (fairscape_models, fairscape_cli, aireadiness_wizard). Reports pass/fail with specific blockers. Invoked by both wizards at step 1 before anything else runs; also user-callable to debug "why doesn't the wizard work". On failure, the wizard offloads to env-setup.
---

# Preflight check

Runs at the very start of either RO-Crate wizard (local or remote) so the user finds out about missing dependencies *before* they've answered fifteen interview questions. Pure read-only — never installs anything. When a check fails, the calling wizard hands off to `env-setup` for the interactive remediation.

## What to tell the user

One sentence, then run the checks:

> *"Quick environment check first — Python version, `fairscape-cli` on PATH, and the three packages the wizard needs. Takes a second; nothing gets installed."*

## The checks

Run these in a single `Bash` call (one Python invocation does most of the work, so it's one process, not seven):

```bash
python3 - <<'PY'
import json, shutil, sys
result = {"python_version": ".".join(map(str, sys.version_info[:3])),
          "python_executable": sys.executable,
          "checks": [], "blockers": [], "warnings": []}

def add(name, ok, detail, blocker=True):
    result["checks"].append({"name": name, "ok": ok, "detail": detail})
    if not ok:
        (result["blockers"] if blocker else result["warnings"]).append(name)

# 1. Python version
ok = sys.version_info >= (3, 10)
add("python>=3.10", ok, result["python_version"])

# 2. fairscape-cli on PATH
binpath = shutil.which("fairscape-cli")
add("fairscape-cli on PATH", binpath is not None, binpath or "not found")

# 3. fairscape_models importable
try:
    import fairscape_models
    from fairscape_models.rocrate import ROCrateV1_2  # the symbol the leaves validate against
    add("fairscape_models importable", True, getattr(fairscape_models, "__version__", "unknown"))
except Exception as e:
    add("fairscape_models importable", False, f"{type(e).__name__}: {e}")

# 4. fairscape_cli importable (the package — distinct from the binary)
try:
    import fairscape_cli
    add("fairscape_cli importable", True, getattr(fairscape_cli, "__version__", "unknown"))
except Exception as e:
    add("fairscape_cli importable", False, f"{type(e).__name__}: {e}")

# 5. aireadiness_wizard importable (this grader)
try:
    import aireadiness_wizard
    from aireadiness_wizard import rubric_eval  # the module agentic-rescore calls
    add("aireadiness_wizard importable", True, getattr(aireadiness_wizard, "__version__", "unknown"))
except Exception as e:
    add("aireadiness_wizard importable", False, f"{type(e).__name__}: {e}")

# 6. Optional: pandas+pyarrow for the summary-stats phase. Warning, not blocker.
try:
    import pandas, pyarrow  # noqa
    add("pandas+pyarrow (for compute-summary-stats)", True, f"pandas={pandas.__version__}", blocker=False)
except Exception as e:
    add("pandas+pyarrow (for compute-summary-stats)", False, f"{type(e).__name__}: {e}", blocker=False)

# 7. Virtualenv detection (informational, never a blocker)
in_venv = sys.prefix != sys.base_prefix or hasattr(sys, "real_prefix")
add("virtualenv active", in_venv, sys.prefix if in_venv else "system Python — env-setup will recommend creating .venv", blocker=False)

result["ok"] = not result["blockers"]
print(json.dumps(result, indent=2))
PY
```

Parse the JSON output. The `ok` field is the single pass/fail signal.

## Reporting to the user

**On pass** — one line, then return:

> *"Preflight OK. Python `<ver>`, fairscape-cli at `<path>`, all packages importable. Continuing."*

If the pandas/pyarrow warning fires, mention it once non-blockingly:

> *"(Note: pandas + pyarrow aren't installed. That only matters if you run `compute-summary-stats` later. The wizard will tell you if it hits it.)"*

**On fail** — list every blocker explicitly, then offer the off-ramp:

```
Preflight blockers:
  ✗ fairscape-cli on PATH         — not found
  ✗ fairscape_models importable   — ModuleNotFoundError: No module named 'fairscape_models'
  ✗ aireadiness_wizard importable   — ModuleNotFoundError: No module named 'aireadiness_wizard'

Want me to walk you through fixing this? I'll run `env-setup` which will ask whether you want a PyPI install (recommended for most users) or an editable dev install from sibling repos, and optionally set up a venv so we don't touch system Python.
```

Then ask:

> *"`env-setup` now, or stop and fix it yourself? (`fix` / `skip`.)"*

- **`fix`** → invoke `env-setup`.
- **`skip`** → exit. Tell the user the exact pip commands they need; do not auto-run anything.

## State

Preflight does not write state. It's a pure check. The wizard that invoked it decides what to do with the result.

## Standalone use

A user can invoke `preflight-check` directly to debug environment issues without starting a wizard. In that case, on pass it should also print:

> *"Ready. Run `/fairscape-remote-rocrate-wizard` or `/fairscape-rocrate-wizard` to start."*

## Don't

- Don't `pip install` anything. That's `env-setup`'s job, and only with explicit user confirmation.
- Don't fail the whole check on pandas/pyarrow missing — that's a warning, the wizard runs fine without it until the user picks `compute-summary-stats`.
- Don't add per-phase preflight (PDF tools, requests, etc.). Keep this skill cheap. Phase-specific deps are surfaced when the phase fails.
- Don't probe the network. No `pip search`, no `pypi.org` reach-out — preflight runs offline. `env-setup` is where network calls live.
- Don't run the checks one at a time in seven separate Bash calls. One Python script, one JSON blob out — faster and atomic.
