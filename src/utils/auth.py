from ..core.state import app_state
from ..network.client import extract_ip_from_user_id

# Which message types require which token scope
EXPECTED_SCOPE = {
    "POST": "broadcast",
    "LIKE": "broadcast",
    "DM": "chat",
    "FOLLOW": "follow",
    "UNFOLLOW": "follow",
    "FILE_OFFER": "file",
    "FILE_CHUNK": "file",
    "GROUP_CREATE": "group",
    "GROUP_UPDATE": "group",
    "GROUP_MESSAGE": "group",
    "TICTACTOE_INVITE": "game",
    "TICTACTOE_MOVE": "game",
    # NOTE: do not require a token for REVOKE, PING, PROFILE, ACK, FILE_RECEIVED
}

def require_valid_token(msg: dict, addr: tuple, verbose: bool=False) -> bool:
    mtype = msg.get("TYPE", "")
    expected = EXPECTED_SCOPE.get(mtype)
    if not expected:
        return True  # no token needed for this type

    token = msg.get("TOKEN")
    if not token:
        if verbose:
            print(f"[AUTH] DROP {mtype}: missing TOKEN")
        return False

    ok, reason = app_state.validate_token(token, expected)
    if not ok:
        if verbose:
            print(f"[AUTH] DROP {mtype}: invalid token ({reason})")
        return False

    # Optional IP hardening (match claimed FROM/USER_ID IP with source addr)
    claimed = msg.get("FROM") or msg.get("USER_ID") or ""
    ip = extract_ip_from_user_id(claimed)
    if ip and ip != addr[0]:
        if verbose:
            print(f"[AUTH] DROP {mtype}: IP mismatch (claimed {ip} vs actual {addr[0]})")
        return False

    return True
