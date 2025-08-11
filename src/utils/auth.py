from ..core.state import app_state
from ..network.client import extract_ip_from_user_id

# Which message types require which token scope
EXPECTED_SCOPE = {
    "DM": "chat",
    "POST": "broadcast",
    "LIKE": "broadcast",
    "FOLLOW": "follow",
    "UNFOLLOW": "follow",
    "FILE_OFFER": "file",
    "FILE_CHUNK": "file",
    "FILE_RECEIVED": None,        # no token in spec
    "GROUP_CREATE": "group",
    "GROUP_UPDATE": "group",
    "GROUP_MESSAGE": "group",
    "TICTACTOE_INVITE": "game",
    "TICTACTOE_MOVE": "game",
    "TICTACTOE_RESULT": "game",
    "PROFILE": None,              # no token
    "PING": None,                 # no token
    "ACK": None,                  # no token
    "REVOKE": None,               # allow through; it *is* the revocation
}

ID_FIELD_MAP = {
    "POST": "USER_ID",
    "PROFILE": "USER_ID",
    "PING": "USER_ID",
    # everything else uses FROM
}

def _sender_user_id(msg_type: str, msg: dict) -> str | None:
    field = ID_FIELD_MAP.get(msg_type, "FROM")
    return msg.get(field)

def require_valid_token(msg: dict, addr: tuple, verbose: bool) -> bool:
    mtype = msg.get("TYPE", "")
    expected_scope = EXPECTED_SCOPE.get(mtype, None)

    # Source IP vs declared user@ip check (Security Considerations)
    uid = _sender_user_id(mtype, msg)
    if uid and "@" in uid:
        declared_ip = uid.split("@", 1)[1]
        if declared_ip != addr[0]:
            # Only show verbose for non-PROFILE messages
            if verbose and mtype not in ("PING", "PROFILE"):
                print(f"DROP ! {mtype}: IP mismatch {declared_ip} != {addr[0]}")
            return False

    # If this type doesn't use tokens, allow it through
    if expected_scope is None:
        return True

    token = msg.get("TOKEN")
    if not token:
        if verbose:
            print(f"DROP ! {mtype}: missing TOKEN")
        return False

    ok, reason = app_state.validate_token(token, expected_scope)
    if not ok:
        if verbose:
            print(f"DROP ! {mtype}: invalid token ({reason})")
        return False

    return True