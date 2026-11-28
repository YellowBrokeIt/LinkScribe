"""Pure request allowlist for the zero-generation native preparation."""
import copy


class NativeContract:
    def __init__(self, requests, queries, model):
        if len(requests) != 6 or len(queries) != 7:
            raise ValueError("Expected the frozen six render requests and seven grammar queries.")
        self.requests = copy.deepcopy(requests)
        self.queries = copy.deepcopy(queries)
        self.model = model
        self.native_port = None
        self.counts = {"version": 0, "show": 0, "render": 0, "tokenize": 0,
                       "grammar": 0, "unload": 0, "residents": 0}
        self.pending_render = None

    def bind_port(self, port):
        if type(port) is not int or port <= 0 or port == 11434:
            raise ValueError("Invalid owned native runner port.")
        if self.native_port is not None and port != self.native_port:
            raise ValueError("Native runner port changed during the fixed stage.")
        self.native_port = port

    def allow(self, path, body, port):
        if port == 11434 and path == "/api/version" and body is None and self.counts["version"] < 120:
            kind = "version"
        elif port == 11434 and path == "/api/show" and body == {"model": self.model} and not self.counts["show"]:
            kind = "show"
        elif port == 11434 and path == "/api/chat" and isinstance(body, dict) and body.get("_debug_render_only") is True:
            index = self.counts["render"]
            if (index >= 6 or self.counts["tokenize"] != index
                    or body != {**self.requests[index]["request"], "_debug_render_only": True}):
                raise ValueError("Native render request changes, repeats or omits the complete frozen messages/schema.")
            kind = "render"
        elif port == self.native_port and port is not None and path == "/tokenize":
            if (not isinstance(self.pending_render, str) or self.counts["tokenize"] + 1 != self.counts["render"]
                    or body != {"content": self.pending_render,
                                "add_special": not self.pending_render.startswith("<|begin_of_text|>"),
                                "parse_special": True}):
                raise ValueError("Tokenization is not exactly the last complete native rendering.")
            kind = "tokenize"
        elif port == self.native_port and port is not None and path == "/completion":
            index = self.counts["grammar"]
            if (index >= 7 or self.counts["render"] != 6 or self.counts["tokenize"] != 6
                    or body != self.queries[index]["request"]
                    or body.get("prompt") != [[]] or type(body.get("n_predict")) is not int
                    or body["n_predict"] != 0):
                raise ValueError("Only the exact ordered empty-prompt, zero-prediction grammar queries are allowed.")
            kind = "grammar"
        elif (port == 11434 and path == "/api/chat" and not self.counts["unload"]
              and body == {"model": self.model, "messages": [], "keep_alive": 0, "stream": False}):
            kind = "unload"
        elif port == 11434 and path == "/api/ps" and body is None and self.counts["unload"] == 1 and not self.counts["residents"]:
            kind = "residents"
        else:
            raise ValueError("Native transport refuses this non-allowlisted request; generation/import/download is unavailable.")
        self.counts[kind] += 1
        return kind

    def observe(self, kind, response):
        if not isinstance(response, dict):
            raise ValueError("Native response is not a JSON object.")
        if kind == "render":
            rendered = response.get("_debug_info", {}).get("rendered_template")
            if (not isinstance(rendered, str) or not rendered or response.get("eval_count", 0)
                    or response.get("prompt_eval_count", 0) or response.get("message", {}).get("content")):
                raise ValueError("Render-only response evaluated/generated text or lacks a complete prompt.")
            self.pending_render = rendered
        elif kind == "tokenize":
            if not isinstance(response.get("tokens"), list):
                raise ValueError("Native tokenization response lacks actual tokens.")
            self.pending_render = None
        elif kind == "grammar":
            if (response.get("content") or response.get("tokens_predicted", 0)
                    or response.get("tokens_evaluated", 0) or response.get("eval_count", 0)
                    or response.get("timings", {}).get("predicted_n", 0)
                    or response.get("timings", {}).get("prompt_n", 0)):
                raise ValueError("A zero-output schema query evaluated or generated tokens.")

    def require_complete(self):
        expected = {"show": 1, "render": 6, "tokenize": 6, "grammar": 7, "unload": 1, "residents": 1}
        if not self.counts["version"] or any(self.counts[k] != v for k, v in expected.items()):
            raise ValueError("Actual native request inventory is incomplete or unexpected.")
