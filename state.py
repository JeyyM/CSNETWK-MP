# state.py
# Shared in-memory state for the listener and handlers.

peer_table = {}      # user_id -> last_seen_time
profile_data = {}    # user_id -> {display_name, status}
user_ip_map = {}     # user_id -> actual IP address
post_feed = []       # list of posts (only those received via broadcast)

# --- Tic Tac Toe state ---
# pending invites addressed to US; key: (from_user, gameid) -> {...}
ttt_invites = {}

# all games we know; gameid -> {...}
ttt_games = {}
