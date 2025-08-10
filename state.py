# state.py
# Shared in-memory state for the listener and handlers.

peer_table = {}      # user_id -> last_seen_time
profile_data = {}    # user_id -> {display_name, status}
user_ip_map = {}     # user_id -> actual IP address
post_feed = []       # list of posts (only those received via broadcast)

# TicTacToe
ttt_games = {}       # gameid -> {board, players, next_symbol, turn, moves_seen:set[int]}

# ACK tracking for retry logic (invite/move)
ack_seen = set()     # set of MESSAGE_IDs we've ACKed (receiver) or have received ACK for (sender)