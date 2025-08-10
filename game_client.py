# game_client.py
import socket, time, uuid, random, re
from protocol import build_message
from state import user_ip_map, ttt_games, ttt_invites, profile_data

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
        if verbose: print(f"[TTT] sent -> {to_uid}@{ip}")
        return True
    finally:
        s.close()

def get_board(gameid: str):
    """Return a string representation of the board for a given gameid."""
    if gameid not in ttt_games:
        return "No such game."

    b = ttt_games[gameid]["board"]
    def c(i): return b[i] if b[i] else str(i)
    return (
        f" {c(0)} | {c(1)} | {c(2)}\n"
        "---------\n"
        f" {c(3)} | {c(4)} | {c(5)}\n"
        "---------\n"
        f" {c(6)} | {c(7)} | {c(8)}"
    )

def start_game_invite(my_uid: str, opp_uid: str, symbol: str, token_game: str, verbose=False):
    symbol = symbol.upper()
    if symbol not in {"X","O"}: raise ValueError("symbol must be X or O")

    gameid = f"g{random.randint(0,255)}"
    mid = uuid.uuid4().hex[:8]
    ts  = int(time.time())

    # preload my local game state (no moves yet)
    other = "O" if symbol == "X" else "X"
    ttt_games[gameid] = {
        "board": [""]*9,
        "players": {symbol: my_uid, other: opp_uid},
        "next_symbol": "X",
        "turn": 1,
        "moves_seen": set(),
    }

    fields = {
        "TYPE": "TICTACTOE_INVITE",
        "FROM": my_uid,
        "TO": opp_uid,
        "GAMEID": gameid,
        "MESSAGE_ID": mid,
        "SYMBOL": symbol,
        "TIMESTAMP": ts,
        "TOKEN": token_game,
    }
    msg = build_message(fields)
    ok = _send_unicast(msg, opp_uid, verbose)
    if not ok and verbose:
        print("[TTT] invite send failed")
    return gameid if ok else None

def send_move(my_uid: str, opp_uid: str, gameid: str, position: int, token_game: str, verbose=False):
    if gameid not in ttt_games:
        if verbose: print("[TTT] unknown game"); return False
    g = ttt_games[gameid]
    board = g["board"]
    if not (0 <= position <= 8) or board[position]:
        if verbose: print("[TTT] invalid position"); return False

    # figure out my symbol
    my_symbol = None
    for s, uid in g["players"].items():
        if uid == my_uid: my_symbol = s; break
    if not my_symbol:
        if verbose: print("[TTT] you are not a player"); return False

    if g["next_symbol"] != my_symbol:
        if verbose: print("[TTT] not your turn"); return False

    turn = g["turn"]
    # apply locally (optimistic UI; peer will also apply)
    board[position] = my_symbol
    g["moves_seen"].add(turn)
    g["turn"] += 1
    g["next_symbol"] = "O" if my_symbol == "X" else "X"

    mid = uuid.uuid4().hex[:8]
    fields = {
        "TYPE": "TICTACTOE_MOVE",
        "FROM": my_uid,
        "TO": opp_uid,
        "GAMEID": gameid,
        "MESSAGE_ID": mid,
        "POSITION": position,
        "SYMBOL": my_symbol,
        "TURN": turn,
        "TOKEN": token_game,
    }
    msg = build_message(fields)
    return _send_unicast(msg, opp_uid, verbose)
