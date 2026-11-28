"""Replace only the schema before the archived native builder and observer."""
from contextlib import contextmanager
import copy


def require_format_only(previous, candidate):
    if (previous == candidate or set(previous) != set(candidate)
            or {k: v for k, v in previous.items() if k != "format"}
            != {k: v for k, v in candidate.items() if k != "format"}):
        raise ValueError("Only the exact frozen native format may change.")


@contextmanager
def grammar_payloads(module, previous, candidate, record, checkpoint):
    require_format_only(previous, candidate)
    builder = module._ollama
    record["grammar_schema_projections"] = []
    record["grammar_payload_builder_restored"] = False
    checkpoint()

    def project(payload):
        expected = {"task": "translation", "messages": previous["messages"],
                    "response_schema": previous["format"]}
        if payload != expected or record["grammar_schema_projections"]:
            raise ValueError("The grammar projection requires one complete unchanged source-spelling payload.")
        projected = copy.deepcopy(payload)
        projected["response_schema"] = copy.deepcopy(candidate["format"])
        record["grammar_schema_projections"].append({"original_app_payload": copy.deepcopy(payload),
                                                    "projected_app_payload": copy.deepcopy(projected),
                                                    "only_response_schema_changed": True})
        checkpoint()
        return builder(projected)

    module._ollama = project
    try:
        yield
        if len(record["grammar_schema_projections"]) != 1:
            raise ValueError("The complete source did not construct exactly one grammar-constrained request.")
    finally:
        module._ollama = builder
        record["grammar_payload_builder_restored"] = True
        checkpoint()
