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

def _print_numbered_grid():
    # Show numbered slots for quick reference
    print("\n 0 | 1 | 2\n-----------\n 3 | 4 | 5\n-----------\n 6 | 7 | 8\n")

def _ack(sock, addr, message_id, verbose):
    if not message_id: return
    msg = build_message({"TYPE":"ACK","MESSAGE_ID":message_id,"STATUS":"RECEIVED"}).encode("utf-8")
    try:
        sock.sendto(msg, addr)
        if verbose: print(f"[TTT] ACK {message_id} -> {addr}")
    except Exception as e:
        if verbose: print(f"[TTT] ACK send failed: {e}")

def handle_tictactoe_invite(msg: dict, addr, sock, verbose: bool):
    # TYPE: TICTACTOE_INVITE
    f = msg.get("FROM"); t = msg.get("TO"); gid = msg.get("GAMEID")
    sym = (msg.get("SYMBOL") or "").upper()
    mid = msg.get("MESSAGE_ID")

    if seen_before(mid):
        if verbose: print(f"DROP dup INVITE {mid}")
        _ack(sock, addr, mid, verbose); return

    if not f or not t or not gid or sym not in {"X","O"}:
        if verbose: print("[TTT] INVITE missing fields"); return

    # learn sender IP
    user_ip_map[f] = addr[0]

    # store invite for the menu
    ttt_invites[(f, gid)] = {
        "from": f, "to": t, "gameid": gid, "symbol": sym, "timestamp": int(time.time())
    }

    # ensure we have a game shell so we can keep state
    if gid not in ttt_games:
        other = "O" if sym == "X" else "X"
        ttt_games[gid] = {
            "board": [""]*9,
            "players": {sym: f, other: t},
            "next_symbol": "X",
            "turn": 1,
            "moves_seen": set(),
        }

    disp = profile_data.get(f, {}).get("display_name", f.split("@")[0])
    print(f"{disp} is inviting you to play tic-tac-toe. (game {gid})")
    # 👉 show numbered grid (not the live board) to help decide first move
    _print_numbered_grid()

    _ack(sock, addr, mid, verbose)

def handle_tictactoe_move(msg: dict, addr, sock, verbose: bool):
    # TYPE: TICTACTOE_MOVE
    f = msg.get("FROM"); gid = msg.get("GAMEID")
    pos_raw = msg.get("POSITION"); sym = (msg.get("SYMBOL") or "").upper()
    turn_raw = msg.get("TURN"); mid = msg.get("MESSAGE_ID")

    if seen_before(mid):
        if verbose: print(f"DROP dup MOVE {mid}")
        _ack(sock, addr, mid, verbose); return

    if not f or not gid or sym not in {"X","O"} or pos_raw is None or turn_raw is None:
        if verbose: print("[TTT] MOVE missing fields"); return
    try:
        pos = int(pos_raw); turn = int(turn_raw)
    except ValueError:
        if verbose: print("[TTT] MOVE invalid ints"); return

    # learn sender IP
    user_ip_map[f] = addr[0]

    # ensure game shell
    if gid not in ttt_games:
        ttt_games[gid] = {"board":[""]*9,"players":{sym:f},"next_symbol":"X","turn":1,"moves_seen":set()}

    g = ttt_games[gid]
    b = g["board"]; players = g["players"]
    if sym not in players: players[sym] = f

    # dup turn guard
    if turn in g["moves_seen"]:
        if verbose: print(f"[TTT] duplicate TURN={turn} for {gid}")
        _ack(sock, addr, mid, verbose); return

    # rule checks
    if g["next_symbol"] != sym or g["turn"] != turn or not (0 <= pos <= 8) or b[pos]:
        if verbose: print("[TTT] invalid/out-of-turn move (ignored)")
        _ack(sock, addr, mid, verbose); return

    # apply the move to our local board/state
    b[pos] = sym
    g["moves_seen"].add(turn)
    g["turn"] += 1
    g["next_symbol"] = "O" if sym == "X" else "X"

    # 👉 don't render the board here; only a brief notice
    disp = profile_data.get(f, {}).get("display_name", f.split("@")[0])
    print(f"{disp} has placed a move in {gid}")

    _ack(sock, addr, mid, verbose)

def handle_tictactoe_result(msg: dict, addr, sock, verbose: bool):
    # TYPE: TICTACTOE_RESULT
    gid = msg.get("GAMEID")
    res = (msg.get("RESULT") or "").upper()  # WIN | LOSS | DRAW | FORFEIT
    sym = (msg.get("SYMBOL") or "").upper()

    print(f"[TTT RESULT] game={gid} result={res} as {sym}")
    if gid in ttt_games:
        _print_board(ttt_games[gid]["board"])

    # If invitee rejected using FORFEIT, or game ended, clean up local book-keeping
    if res in {"FORFEIT","DRAW","WIN","LOSS"}:
        # remove any invite entries for this gid
        for key in list(ttt_invites.keys()):
            if key[1] == gid:
                del ttt_invites[key]
        # optional: drop finished game (your choice to keep/dump board on draw)
        if gid in ttt_games and res != "DRAW":
            pass
