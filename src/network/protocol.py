"""LSNP Protocol implementation."""


def parse_message(raw: str) -> dict:
    """
    Parse an LSNP message into a dict.
    Tolerates \\r\\n line endings and extra trailing whitespace.
    Only the header before the first blank line is parsed.
    Returns {} if the message doesn't contain a proper blank-line terminator.
    """
    if not isinstance(raw, str):
        return {}

    # Normalize line endings to \n
    raw_norm = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Require at least one blank-line separator somewhere
    if "\n\n" not in raw_norm:
        return {}

    header, _ = raw_norm.split("\n\n", 1)  # parse only up to the first blank line

    msg = {}
    for line in header.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            msg[k.strip()] = v.strip()
    return msg


def build_message(fields: dict) -> str:
    """
    Build an LSNP message string from fields, guaranteeing a blank-line terminator.
    """
    if not isinstance(fields, dict):
        raise TypeError("fields must be a dict")

    body = "".join(f"{k}: {v}\n" for k, v in fields.items())
    return body + "\n"  # => ensures final "\n\n"
