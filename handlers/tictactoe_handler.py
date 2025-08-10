# handlers/tictactoe_handler.py
import time

from protocol import build_message
from state import ttt_games, profile_data, user_ip_map, ack_seen
from dedupe import seen_before

WIN_LINES = [
    (0,1,2), (3,4,5), (6,7,8),   # rows
    (0,3,6), (1,4,7), (2,5,8),   # cols
    (0,4,8), (2,4,6),            # diags
]

def _print_board(board):
    def cell(i): return board[i] if board[i] else " "
    print(f"\n {cell(0)} | {cell(1)} | {cell(2)}")
    print("-----------")
    print(f" {cell(3)} | {cell(4)} | {cell(5)}")
    print("-----------")
    print(f" {cell(6)} | {cell(7)} | {cell(8)}\n")

def _send_ack(sock, addr, message_id, verbose):
    ack = build_message({"TYPE": "ACK", "MESSAGE_ID": message_id, "STATUS": "RECEIVED"}).encode("utf-8")
    try:
        sock.sendto(ack, addr)
        if verbose:
            print(f"[TTT] ACK sent for {message_id} to {addr}")
    except Exception as e:
        if verbose:
            print(f"[TTT] ACK send failed: {e}")

def handle_ttt_invite(msg: dict, addr, sock, verbose: bool):
    """TYPE: TICTACTOE_INVITE (unicast)"""
    from_user = msg.get("FROM")
    to_user   = msg.get("TO")
    gid       = msg.get("GAMEID")
    symbol    = msg.get("SYMBOL", "X").upper()
    mid       = msg.get("MESSAGE_ID")

    if not from_user or not gid or symbol not in {"X","O"}:
        if verbose: print("[TTT] INVITE missing fields")
        return

    # Duplicate suppression by MESSAGE_ID
    if seen_before(mid):
        if verbose: print(f"DROP! duplicate INVITE {mid}")
        _send_ack(sock, addr, mid, verbose)  # idempotent: ACK again
        return

    # Learn sender IP
    user_ip_map[from_user] = addr[0]

    # If game does not exist, create it
    if gid not in ttt_games:
        # Who plays what: inviter chose SYMBOL; invitee gets the other
        other = "O" if symbol == "X" else "X"
        ttt_games[gid] = {
            "board": [""]*9,
            "players": {
                symbol: from_user,   # inviter
                other:  to_user,     # invitee (us)
            },
            "next_symbol": "X",      # X always starts
            "turn": 1,
            "moves_seen": set(),     # set of TURN numbers processed
        }

    display = profile_data.get(from_user, {}).get("display_name", from_user.split("@")[0])
    print(f"{display} is inviting you to play tic-tac-toe. (game {gid})")
    _print_board(ttt_games[gid]["board"])

    # ACK the invite
    if mid:
        ack_seen.add(mid)  # mark we've seen/ACKed
        _send_ack(sock, addr, mid, verbose)

def handle_ttt_move(msg: dict, addr, sock, verbose: bool):
    """TYPE: TICTACTOE_MOVE (unicast both ways)"""
    from_user = msg.get("FROM")
    to_user   = msg.get("TO")
    gid       = msg.get("GAMEID")
    pos_raw   = msg.get("POSITION")
    symbol    = (msg.get("SYMBOL") or "").upper()
    turn_raw  = msg.get("TURN")
    mid       = msg.get("MESSAGE_ID")

    # Dedup by MESSAGE_ID
    if seen_before(mid):
        if verbose: print(f"DROP! duplicate MOVE id={mid}")
        _send_ack(sock, addr, mid, verbose)
        return

    # Basic validation
    if not from_user or gid is None or pos_raw is None or symbol not in {"X","O"} or turn_raw is None:
        if verbose: print("[TTT] MOVE missing fields")
        return

    try:
        pos  = int(pos_raw)
        turn = int(turn_raw)
    except ValueError:
        if verbose: print("[TTT] MOVE bad ints")
        return

    if gid not in ttt_games:
        # Late join: create minimal game state (we'll trust the first sender layout)
        ttt_games[gid] = {"board":[""]*9, "players":{symbol:from_user}, "next_symbol":"X", "turn":1, "moves_seen":set()}

    g = ttt_games[gid]
    board = g["board"]
    players = g["players"]

    # Learn IP of sender
    user_ip_map[from_user] = addr[0]

    # dup detection by (GAMEID, TURN)
    if turn in g["moves_seen"]:
        if verbose: print(f"[TTT] duplicate TURN={turn} for {gid} (idempotent ACK)")
        _send_ack(sock, addr, mid, verbose)
        return

    # Rules: check sender matches assigned symbol, turn order, empty cell
    if players.get(symbol) != from_user:
        if verbose: print("[TTT] symbol/player mismatch – ignoring for game logic")
        _send_ack(sock, addr, mid, verbose)
        return

    if g["next_symbol"] != symbol or g["turn"] != turn:
        if verbose: print("[TTT] out-of-turn move – ignoring for game logic")
        _send_ack(sock, addr, mid, verbose)
        return

    if not (0 <= pos <= 8) or board[pos]:
        if verbose: print("[TTT] invalid position")
        _send_ack(sock, addr, mid, verbose)
        return

    # Apply move
    board[pos] = symbol
    g["moves_seen"].add(turn)

    # Advance turn
    g["turn"] += 1
    g["next_symbol"] = "O" if symbol == "X" else "X"

    # Show board
    _print_board(board)

    # ACK the move
    if mid:
        ack_seen.add(mid)
        _send_ack(sock, addr, mid, verbose)

def handle_ttt_result(msg: dict, addr, sock, verbose: bool):
    """TYPE: TICTACTOE_RESULT (unicast)"""
    gid     = msg.get("GAMEID")
    result  = (msg.get("RESULT") or "").upper()   # WIN | LOSS | DRAW | FORFEIT
    symbol  = (msg.get("SYMBOL") or "").upper()
    wline   = msg.get("WINNING_LINE", "")
    mid     = msg.get("MESSAGE_ID")

    if gid not in ttt_games:
        ttt_games[gid] = {"board":[""]*9, "players":{}, "next_symbol":"X", "turn":1, "moves_seen":set()}

    print(f"[TTT RESULT] game={gid} result={result} as {symbol} winning_line={wline}")
    _print_board(ttt_games[gid]["board"])

    # No state change needed (terminal message)
    # No ACK required by RFC here, but harmless if you want to add one.
