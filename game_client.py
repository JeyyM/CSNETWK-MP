# game_client.py
import socket, time, uuid, random, re
from protocol import build_message
from state import user_ip_map, ttt_games, ack_seen, profile_data

PORT = 50999

def _ip_from_uid(uid: str):
    if "@" not in uid: return None
    ip = uid.split("@",1)[1].strip()
    return ip if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) else None

def _send_unicast(msg_str: str, to_uid: str, verbose=False):
    ip = user_ip_map.get(to_uid) or _ip_from_uid(to_uid)
    if not ip:
        if verbose: print(f"[TTT] no IP for {to_uid}")
        return False
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.sendto(msg_str.encode("utf-8"), (ip, PORT))
        if verbose: print(f"[TTT] sent to {to_uid} @ {ip}")
        return True
    finally:
        s.close()

def _retry_send_wait_ack(msg_str: str, to_uid: str, message_id: str, retries=3, timeout=2.0, verbose=False):
    for attempt in range(1, retries+1):
        _send_unicast(msg_str, to_uid, verbose)
        start = time.time()
        while time.time() - start < timeout:
            if message_id in ack_seen:
                return True
            time.sleep(0.05)
        if verbose:
            print(f"[TTT] no ACK for {message_id} (attempt {attempt}/{retries})")
    return False

def start_game_invite(my_uid: str, my_display: str, opponent_uid: str, symbol: str, token_game: str, verbose=False):
    """Create local game and send INVITE (unicast, retry w/ ACK). Returns gameid or None."""
    symbol = symbol.upper()
    if symbol not in {"X","O"}:
        raise ValueError("symbol must be X or O")

    gameid = f"g{random.randint(0,255)}"
    mid = uuid.uuid4().hex[:8]
    ts  = int(time.time())

    # Initialize my local state
    other = "O" if symbol == "X" else "X"
    ttt_games[gameid] = {
        "board": [""]*9,
        "players": {symbol: my_uid, other: opponent_uid},
        "next_symbol": "X",
        "turn": 1,
        "moves_seen": set(),
    }

    fields = {
        "TYPE": "TICTACTOE_INVITE",
        "FROM": my_uid,
        "TO": opponent_uid,
        "GAMEID": gameid,
        "MESSAGE_ID": mid,
        "SYMBOL": symbol,
        "TIMESTAMP": ts,
        "TOKEN": token_game,
    }
    msg = build_message(fields)

    ok = _retry_send_wait_ack(msg, opponent_uid, mid, retries=3, timeout=2.0, verbose=verbose)
    if not ok and verbose:
        print("[TTT] Invite failed (no ACK). You can still retry from menu.")
    return gameid if ok else None

def send_move(my_uid: str, opponent_uid: str, gameid: str, position: int, verbose=False, token_game: str=""):
    """Apply my move locally, then send MOVE (unicast, retry w/ ACK)."""
    if gameid not in ttt_games:
        if verbose: print("[TTT] unknown game")
        return False

    g = ttt_games[gameid]
    board = g["board"]
    if not (0 <= position <= 8) or board[position]:
        if verbose: print("[TTT] invalid position")
        return False

    my_symbol = None
    for s, uid in g["players"].items():
        if uid == my_uid:
            my_symbol = s
            break
    if not my_symbol:
        if verbose: print("[TTT] you are not a player in this game")
        return False

    if g["next_symbol"] != my_symbol:
        if verbose: print("[TTT] not your turn")
        return False

    # Apply locally
    board[position] = my_symbol
    turn = g["turn"]
    g["moves_seen"].add(turn)
    g["turn"] += 1
    g["next_symbol"] = "O" if my_symbol == "X" else "X"

    # Build and send MOVE
    mid = uuid.uuid4().hex[:8]
    fields = {
        "TYPE": "TICTACTOE_MOVE",
        "FROM": my_uid,
        "TO": opponent_uid,
        "GAMEID": gameid,
        "MESSAGE_ID": mid,
        "POSITION": position,
        "SYMBOL": my_symbol,
        "TURN": turn,
        "TOKEN": token_game,
    }
    msg = build_message(fields)
    ok = _retry_send_wait_ack(msg, opponent_uid, mid, retries=3, timeout=2.0, verbose=verbose)
    return ok

def get_board(gameid: str):
    g = ttt_games.get(gameid)
    return g["board"][:] if g else None
