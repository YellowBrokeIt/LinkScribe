"""Bounded subprocess receipts for the one declared build and validator calls."""
import os
from pathlib import Path
import selectors
import subprocess
import time

from context import save, record, utc, event


def run_command(argv, environment, cwd, output_base, timeout, capture_limit):
    base = Path(output_base)
    paths = {name: base.with_name(base.name + "-" + name) for name in
             ("stdout.bin", "stderr.bin", "command.json")}
    if any(path.exists() for path in paths.values()):
        raise ValueError("Refusing to repeat or overwrite a command receipt.")
    if not argv or not all(isinstance(s, str) for s in argv) or timeout <= 0:
        raise ValueError("Invalid bounded command.")
    receipt = {"schema_version": 1, "argv": argv, "environment": environment,
               "cwd": str(cwd), "started_at": utc(), "complete": False,
               "timeout_seconds": timeout, "capture_limit_bytes_per_stream": capture_limit}
    save(paths["command.json"], receipt)
    outputs = {"stdout": bytearray(), "stderr": bytearray()}
    process = None
    began = time.monotonic()
    error = None
    selector = selectors.DefaultSelector()
    event("case_start", id=base.name)
    try:
        with paths["stdout.bin"].open("xb") as out, paths["stderr.bin"].open("xb") as err:
            process = subprocess.Popen(argv, cwd=str(cwd), env=environment,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=False)
            receipt["pid"] = process.pid
            for name, pipe, stream in (("stdout", process.stdout, out), ("stderr", process.stderr, err)):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, (name, stream))
            while selector.get_map():
                if time.monotonic() - began > timeout:
                    raise TimeoutError("Bounded command exceeded its fixed deadline.")
                for key, _ in selector.select(timeout=0.02):
                    block = os.read(key.fd, 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    name, stream = key.data
                    available = capture_limit - len(outputs[name])
                    kept = block[:available]
                    stream.write(kept); stream.flush(); outputs[name].extend(kept)
                    if len(block) > available:
                        raise ValueError("Bounded command capture limit exceeded; retained prefix is not complete output.")
            receipt["exit_code"] = process.wait(timeout=max(0.01, timeout - (time.monotonic() - began)))
            receipt["complete"] = True
    except BaseException as exc:
        error = exc
        receipt["error"] = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        selector.close()
        if process is not None:
            if process.poll() is None:
                process.kill()
            try:
                receipt["exit_code"] = process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                receipt["complete"] = False
                receipt["child_wait_failed"] = True
            for stream in (process.stdout, process.stderr):
                stream.close()
        receipt["elapsed_seconds"] = round(time.monotonic() - began, 6)
        receipt["finished_at"] = utc()
        receipt["raw_streams"] = {name: record(paths[name + ".bin"]) for name in outputs
                                  if paths[name + ".bin"].exists()}
        receipt["descendant_cleanup_scope"] = "The outer reviewed process-group monitor owns all descendants, including surviving children."
        save(paths["command.json"], receipt)
        event("case_failed" if error else "case_complete", id=base.name,
              exit_code=receipt.get("exit_code"), complete=receipt["complete"])
    if error:
        raise error
    return receipt, bytes(outputs["stdout"]), bytes(outputs["stderr"])
