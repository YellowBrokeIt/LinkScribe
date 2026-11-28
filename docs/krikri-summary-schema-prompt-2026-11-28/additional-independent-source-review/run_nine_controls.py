"""Run only the nine reviewed synthetic controls with native paths forbidden."""
import runpy
import sys
from pathlib import Path

FORBIDDEN_IMPORTS = {"torch", "transformers", "tokenizers", "tensorflow", "onnxruntime", "gliner", "llama_cpp"}


def audit(event, args):
    if event in {"subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "socket.connect",
                 "socket.connect_ex", "socket.bind", "socket.sendto", "socket.getaddrinfo"}:
        raise AssertionError("Native/network execution forbidden in independent source controls: " + event)
    if event == "import" and str(args[0]).split(".", 1)[0] in FORBIDDEN_IMPORTS:
        raise AssertionError("Model/tokenizer import forbidden in independent source controls: " + str(args[0]))


sys.addaudithook(audit)
candidate = Path(__file__).resolve().parent.parent / "LinkScribe/docs/krikri-summary-schema-prompt-2026-11-28"
sys.path.insert(0, str(candidate))
sys.argv = [str(candidate / "test_protocol.py"), "-v"]
runpy.run_path(str(candidate / "test_protocol.py"), run_name="__main__")
