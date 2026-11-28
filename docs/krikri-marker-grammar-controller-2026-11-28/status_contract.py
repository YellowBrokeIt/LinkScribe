"""Proposed strict interpretation of the unchanged official validator CLI.

This helper is prepared for review. No validator, converter or native call is
performed on import or by this file. Exit zero alone never means accepted.
"""

ACCEPTED = b"Input string is valid according to the grammar.\n"
REJECTED = b"Input string is invalid according to the grammar."
MAX_CAPTURE_BYTES = 65536


def classify(returncode, stdout, stderr):
    if (type(returncode) is not int or not isinstance(stdout, bytes)
            or not isinstance(stderr, bytes)
            or len(stdout) > MAX_CAPTURE_BYTES or len(stderr) > MAX_CAPTURE_BYTES):
        raise ValueError("Invalid or oversized validator process receipt.")
    if returncode != 0 or stderr:
        raise ValueError("Validator initialization, process or diagnostic failure.")
    if stdout == ACCEPTED:
        return "accepted"
    lines = stdout.splitlines()
    if (len(lines) >= 5 and lines[0] == REJECTED
            and lines[1].startswith(b"Error: ")
            and lines[2] == b"" and lines[3] == b"Input string:"):
        return "rejected"
    raise ValueError("Validator did not provide an exact, unambiguous status receipt.")
