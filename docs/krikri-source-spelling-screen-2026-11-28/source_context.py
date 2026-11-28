"""Bind the reviewed spelling map before the existing native payload builder.

No inference, tokenizer, detector, network or model load occurs on import.
The compact output representation and all restoration guards stay unchanged.
"""
from contextlib import contextmanager
import copy
import importlib.util
from pathlib import Path

from protection import restore_segments

PROPOSAL = Path(__file__).resolve().parents[1] / "krikri-source-spelling-context-2026-11-28/prepare_context.py"
_spec = importlib.util.spec_from_file_location("reviewed_source_spelling_projection", PROPOSAL)
_proposal = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_proposal)


def bind_source_context(bundle, context_map):
    """Require the entire original source/map, not just a name or tag match."""
    restored, _ = restore_segments(bundle, bundle["masked_segments"])
    if restored != bundle["source_segments"]:
        raise ValueError("The compact source fails exact source/metadata reversibility.")
    if (context_map["source_segments"] != bundle["source_segments"]
            or context_map["source_segments_sha256"] != bundle["source_segments_sha256"]
            or context_map["compact_protection_binding_sha256"] != bundle["protection_binding_sha256"]
            or context_map["compact_segments"] != bundle["masked_segments"]
            or context_map["context_map"] != _proposal.source_spelling_map(bundle)):
        raise ValueError("The complete source-spelling context differs from its frozen source/map binding.")
    return copy.deepcopy(context_map["context_map"])


@contextmanager
def source_context_payloads(module, bundle, context_map, record, checkpoint):
    """Project one actual application payload before request construction.

The existing transport observer subsequently sees and verifies the entire new
native request. No response is read, rewritten or repaired here.
"""
    spellings = bind_source_context(bundle, context_map)
    native_payload_builder = module._ollama
    record["source_context_map"] = spellings
    record["source_context_projections"] = []
    record["native_payload_builder_restored"] = False
    checkpoint()

    def add_context(payload):
        if record["source_context_projections"]:
            raise ValueError("The fixed complete-source case may project exactly one request; no fragmentation or retry.")
        projected, actual_spellings, combined_bytes = _proposal.project_payload(payload, bundle)
        if actual_spellings != spellings:
            raise ValueError("Actual projected spelling data differs from the frozen source map.")
        record["source_context_projections"].append({
            "original_app_payload": copy.deepcopy(payload),
            "projected_app_payload": copy.deepcopy(projected),
            "source_spellings": copy.deepcopy(actual_spellings),
            "combined_source_json_bytes": combined_bytes,
            "inserted_before_native_request_builder_and_observer": True,
        })
        checkpoint()
        return native_payload_builder(projected)

    module._ollama = add_context
    try:
        yield
        if len(record["source_context_projections"]) != 1:
            raise ValueError("The fixed case did not construct its one complete source-context request.")
    finally:
        module._ollama = native_payload_builder
        record["native_payload_builder_restored"] = True
        checkpoint()
