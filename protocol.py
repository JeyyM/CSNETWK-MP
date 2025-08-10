# protocol.py
# Generic LSNP parser/builder enforcing RFC rules

def parse_message(raw: str) -> dict:
    """
    Parse an LSNP message into a dict.
    Returns {} if the message is malformed (e.g., missing '\\n\\n').
    """
    if not isinstance(raw, str):
        return {}

    # Enforce the required blank-line terminator
    if not raw.endswith("\n\n"):
        return {}

    msg = {}
    for line in raw.strip().splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            msg[k.strip()] = v.strip()
    return msg


def build_message(fields: dict) -> str:
    """
    Build an LSNP message string from a mapping of fields.
    Ensures the RFC-required blank line terminator is present.
    """
    if not isinstance(fields, dict):
        raise TypeError("fields must be a dict")

    # Keep insertion order of dict for readability
    body = "".join(f"{k}: {v}\n" for k, v in fields.items())
    return body + "\n"
