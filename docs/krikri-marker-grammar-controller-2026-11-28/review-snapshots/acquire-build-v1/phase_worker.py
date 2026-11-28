"""One monitored, root-receipted setup phase; no translation worker exists."""
import argparse
import signal
import time

from context import HERE, PHASES, read, sha, save, utc, event, verify_tools, require_storage
from execution_gate import authorize_phase, verify_controller_parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=PHASES, required=True)
    phase = parser.parse_args().phase
    receipt, plan, native, completed_elapsed = authorize_phase(phase)
    claim = verify_controller_parent(phase)
    verify_tools(plan["extra_tool_bindings"]); require_storage()
    output = HERE / (phase + ".json")
    if output.exists():
        raise ValueError("Refusing to overwrite a phase attempt.")
    report = {"schema_version": 1, "phase": phase, "started_at": utc(), "complete": False,
              "plan_sha256": sha(HERE / "plan.json"), "authorization_sha256": sha(HERE / (phase + "-authorization.json")),
              "claim_sha256": sha(HERE / (phase + "-claim.json")), "generation_calls": 0,
              "network_model_downloads": 0, "actions": []}
    save(output, report)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt("Outer supervisor stopped the phase.")))
    began = time.monotonic()
    try:
        if phase == "native_prepare":
            from native_actions import native_prepare
            native_prepare(report, output, plan)
        else:
            event("initialized", phase=phase, model_loads=0)
            from phase_actions import acquire, build, validate
            {"acquire": acquire, "build": build, "validate": validate}[phase](report, output, plan)
        require_storage(); verify_tools(plan["extra_tool_bindings"])
        report["complete"] = True
    except BaseException as error:
        report["error"] = {"type": type(error).__name__, "message": str(error)}
        report["complete"] = False
    finally:
        report["elapsed_seconds"] = round(time.monotonic() - began, 6)
        report["finished_at"] = utc()
        save(output, report)
    event("phase_complete", phase=phase, complete=report["complete"], error=report.get("error"))
    return int(not report["complete"])


if __name__ == "__main__":
    raise SystemExit(main())
