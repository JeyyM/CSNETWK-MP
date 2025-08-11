from ..core.state import app_state
from ..network.client import extract_ip_from_user_id

EXPECTED_SCOPE = {
    "DM": "chat",
    "POST": "broadcast",
    "LIKE": "broadcast",
    "FOLLOW": "follow",
    "UNFOLLOW": "follow",
    "FILE_OFFER": "file",
    "FILE_CHUNK": "file",
    "FILE_RECEIVED": None,
    "GROUP_CREATE": "group",
    "GROUP_UPDATE": "group",
    "GROUP_MESSAGE": "group",
    "TICTACTOE_INVITE": "game",
    "TICTACTOE_MOVE": "game",
    "TICTACTOE_RESULT": "game",
    "PROFILE": None,
    "PING": None,
    "ACK": None,
    "REVOKE": None,
}

ID_FIELD_MAP = {"POST": "USER_ID", "PROFILE": "USER_ID", "PING": "USER_ID"}

def _sender_user_id(msg_type: str, msg: dict) -> str | None:
    field = ID_FIELD_MAP.get(msg_type, "FROM")
    return msg.get(field)

def require_valid_token(msg: dict, addr: tuple, verbose: bool) -> bool:
    mtype = msg.get("TYPE", "")
    expected_scope = EXPECTED_SCOPE.get(mtype, None)

    uid = _sender_user_id(mtype, msg)
    declared_ip = uid.split("@", 1)[1] if uid and "@" in uid else None

    # Only ENFORCE IP match for token-bearing message types
    if expected_scope is not None and declared_ip:
        if declared_ip != addr[0]:
            if verbose:
                print(f"DROP ! {mtype}: IP mismatch {declared_ip} != {addr[0]}")
            return False
    else:
        # Presence/ack/revoke/etc.: warn but accept
        if verbose and declared_ip and declared_ip != addr[0]:
            print(f"WARN ? {mtype}: IP mismatch {declared_ip} != {addr[0]} (accepted)")

    # Types without tokens are allowed through
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
