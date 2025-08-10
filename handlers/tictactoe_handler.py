# handlers/tictactoe_handler.py
import time, socket
from protocol import build_message
from state import user_ip_map, profile_data, ttt_invites, ttt_games
from dedupe import seen_before

PORT = 50999
WIN_LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]

def _print_board(board):
    def c(i): return board[i] if board[i] else " "
    print(f"\n {c(0)} | {c(1)} | {c(2)}\n-----------\n {c(3)} | {c(4)} | {c(5)}\n-----------\n {c(6)} | {c(7)} | {c(8)}\n")

def _ack(sock, addr, message_id, verbose):
    if not message_id:
        return
    msg = build_message({"TYPE":"ACK","MESSAGE_ID":message_id,"STATUS":"RECEIVED"}).encode("utf-8")
    try:
        sock.sendto(msg, addr)
        if verbose: print(f"[TTT] ACK {message_id} -> {addr}")
    except Exception as e:
        if verbose: print(f"[TTT] ACK send failed: {e}")

def _send_unicast_str(msg_str: str, to_ip: str, verbose=False):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.sendto(msg_str.encode("utf-8"), (to_ip, PORT))
        if verbose: print(f"[TTT] sent -> {to_ip}")
    finally:
        s.close()

def handle_tictactoe_invite(msg: dict, addr, sock, verbose: bool):
    # TYPE: TICTACTOE_INVITE
    f = msg.get("FROM"); t = msg.get("TO"); gid = msg.get("GAMEID")
    sym = (msg.get("SYMBOL") or "").upper()
    mid = msg.get("MESSAGE_ID")

    if seen_before(mid):
        if verbose: print(f"DROP dup INVITE {mid}")
        _ack(sock, addr, mid, verbose)
        return

    if not f or not t or not gid or sym not in {"X","O"}:
        if verbose: print("[TTT] INVITE missing fields")
        return

    # learn sender IP
    user_ip_map[f] = addr[0]

    # store invite; accept will be done from main menu
    ttt_invites[(f, gid)] = {
        "from": f, "to": t, "gameid": gid, "symbol": sym, "timestamp": int(time.time())
    }

    disp = profile_data.get(f, {}).get("display_name", f.split("@")[0])
    print(f"{disp} is inviting you to play tic-tac-toe. (game {gid})")

    _ack(sock, addr, mid, verbose)

def handle_tictactoe_move(msg: dict, addr, sock, verbose: bool):
    # TYPE: TICTACTOE_MOVE
    f = msg.get("FROM"); t = msg.get("TO"); gid = msg.get("GAMEID")
    pos_raw = msg.get("POSITION"); sym = (msg.get("SYMBOL") or "").upper()
    turn_raw = msg.get("TURN"); mid = msg.get("MESSAGE_ID")

    if seen_before(mid):
        if verbose: print(f"DROP dup MOVE {mid}")
        _ack(sock, addr, mid, verbose)
        return

    if not f or not t or not gid or sym not in {"X","O"} or pos_raw is None or turn_raw is None:
        if verbose: print("[TTT] MOVE missing fields")
        return

    user_ip_map[f] = addr[0]

    try:
        pos = int(pos_raw); turn = int(turn_raw)
    except ValueError:
        if verbose: print("[TTT] MOVE invalid ints")
        return

    # game skeleton if missing
    if gid not in ttt_games:
        ttt_games[gid] = {"board":[""]*9,"players":{sym:f},"next_symbol":"X","turn":1,"moves_seen":set()}

    g = ttt_games[gid]
    board = g["board"]; players = g["players"]
    # ensure players map contains sender
    if sym not in players: players[sym] = f

    # duplicate turn guard
    if turn in g["moves_seen"]:
        if verbose: print(f"[TTT] duplicate TURN={turn} for {gid} (idempotent)")
        _ack(sock, addr, mid, verbose)
        return

    # rule checks: correct player/symbol, correct turn, empty cell
    if players.get(sym) != f:
        if verbose: print("[TTT] symbol vs sender mismatch (ignored for logic)")
        _ack(sock, addr, mid, verbose); return
    if g["next_symbol"] != sym or g["turn"] != turn:
        if verbose: print("[TTT] out-of-turn move (ignored for logic)")
        _ack(sock, addr, mid, verbose); return
    if not (0 <= pos <= 8) or board[pos]:
        if verbose: print("[TTT] invalid pos")
        _ack(sock, addr, mid, verbose); return

    # apply
    board[pos] = sym
    g["moves_seen"].add(turn)
    g["turn"] += 1
    g["next_symbol"] = "O" if sym == "X" else "X"

    _print_board(board)
    _ack(sock, addr, mid, verbose)

def handle_tictactoe_result(msg: dict, addr, sock, verbose: bool):
    gid = msg.get("GAMEID")
    res = (msg.get("RESULT") or "").upper()
    sym = (msg.get("SYMBOL") or "").upper()
    wline = msg.get("WINNING_LINE","")
    print(f"[TTT RESULT] game={gid} result={res} as {sym} line={wline}")
    if gid in ttt_games:
        _print_board(ttt_games[gid]["board"])
