"""Central application state management."""
from typing import Dict, List, Set, Optional, Callable
import threading
from threading import Lock
import time

from ..models.user import Peer, DirectMessage, Post
from ..models.game import TicTacToeInvite, TicTacToeGame
from ..models.group import Group, GroupMessage

class ApplicationState:
    """Centralized application state manager."""
    
    def __init__(self):
        self._lock = Lock()

        # Network state
        self._peers: Dict[str, Peer] = {}
        self._user_ip_map: Dict[str, str] = {}

        # Social features
        self._following: Set[str] = set()
        self._post_feed: List[Post] = []
        self._dm_history: Dict[str, List[DirectMessage]] = {}
        self._active_dm_user: Optional[str] = None

        # Game state
        self._ttt_invites: Dict[tuple, TicTacToeInvite] = {}
        self._ttt_games: Dict[str, TicTacToeGame] = {}
        
        # Group state
        self._groups: Dict[str, Group] = {}
        self._group_messages: Dict[str, List[GroupMessage]] = {}

        # File offer listeners (UI callbacks)
        self._incoming_file_listeners: List[Callable[[str, dict], None]] = []
        self._pending_acks: Dict[str, threading.Event] = {}
        
        self._suppressed_peers: Dict[str, float] = {}  # user_id -> suppress_until_ts
        self._presence_token: Optional[str] = None
        self._revoked_tokens: Dict[str, float] = {}  # token -> expiry_ts
        self._issued_tokens: Set[str] = set()       # tokens we've sent

        self._local_user_id: Optional[str] = None

    # Revoking
    def _sweep_suppressed(self) -> None:
        now = time.time()
        expired = [u for u, ts in self._suppressed_peers.items() if ts <= now]
        for u in expired:
            self._suppressed_peers.pop(u, None)

    def suppress_peer(self, user_id: str, seconds: int = 60) -> None:
        """Hide a peer from active lists for N seconds."""
        with self._lock:
            self._suppressed_peers[user_id] = time.time() + seconds

    def unsuppress_peer(self, user_id: str) -> None:
        with self._lock:
            self._suppressed_peers.pop(user_id, None)
    
    def get_active_peers(self, exclude_user_id: Optional[str] = None) -> List[Peer]:
        """Get all active (recent) peers, excluding suppressed ones."""
        with self._lock:
            self._sweep_suppressed()
            now = time.time()
            peers = [
                p for p in self._peers.values()
                if p.is_active and not (p.user_id in self._suppressed_peers and self._suppressed_peers[p.user_id] > now)
            ]
            if exclude_user_id:
                peers = [p for p in peers if p.user_id != exclude_user_id]
            return peers

    def _sweep_revoked(self) -> None:
        now = time.time()
        to_del = [tok for tok, exp in self._revoked_tokens.items() if exp <= now]
        for tok in to_del:
            self._revoked_tokens.pop(tok, None)

    def register_issued_token(self, token: str) -> None:
        with self._lock:
            self._issued_tokens.add(token)

    def parse_token(self, token: str):
        """Return (user_id, expiry_ts:int, scope) or None if malformed."""
        try:
            user_id, exp_str, scope = token.split("|", 3)[:3]
            return user_id, int(exp_str), scope
        except Exception:
            return None

    def get_revocable_tokens(self) -> list[str]:
        """Tokens we issued that are still in the future (worth revoking)."""
        now = int(time.time())
        with self._lock:
            out = []
            for tok in self._issued_tokens:
                parsed = self.parse_token(tok)
                if parsed and parsed[1] > now:
                    out.append(tok)
            return out

    def revoke_token(self, token: str) -> None:
        parsed = self.parse_token(token)
        if not parsed:
            return
        _, expiry, _ = parsed
        with self._lock:
            self._revoked_tokens[token] = float(expiry)

    def is_token_revoked(self, token: str) -> bool:
        now = time.time()
        with self._lock:
            # sweep expired revocations
            for t in [t for t,e in self._revoked_tokens.items() if e <= now]:
                self._revoked_tokens.pop(t, None)
            return token in self._revoked_tokens

    def validate_token(self, token: str, expected_scope: str) -> tuple[bool, str]:
        """Check (not expired, scope matches, not revoked). Returns (ok, reason)."""
        parsed = self.parse_token(token)
        if not parsed:
            return False, "malformed"
        user_id, expiry, scope = parsed
        now = int(time.time())
        if now > expiry:
            return False, "expired"
        if scope != expected_scope:
            return False, "scope_mismatch"
        if self.is_token_revoked(token):
            return False, "revoked"
        return True, ""
    
    # Peer management
    def add_peer(self, peer: Peer) -> None:
        """Add or update a peer."""
        with self._lock:
            self._peers[peer.user_id] = peer
            self._user_ip_map[peer.user_id] = peer.ip
    
    def get_peer(self, user_id: str) -> Optional[Peer]:
        """Get a peer by user ID."""
        with self._lock:
            return self._peers.get(user_id)
    
    def get_peer_ip(self, user_id: str) -> Optional[str]:
        """Get IP address for a user."""
        with self._lock:
            return self._user_ip_map.get(user_id)
    
    def update_peer_ip(self, user_id: str, ip: str) -> None:
        """Update IP address for a user."""
        with self._lock:
            self._user_ip_map[user_id] = ip
    
    def set_presence_token(self, token: str) -> None:
        with self._lock:
            self._presence_token = token
            self._issued_tokens.add(token)  # so you can revoke it later

    def get_presence_token(self) -> Optional[str]:
        with self._lock:
            return self._presence_token

    def remove_peer(self, user_id: str) -> None:
        with self._lock:
            self._peers.pop(user_id, None)
            self._user_ip_map.pop(user_id, None)
    
    # Following management
    def follow_user(self, user_id: str) -> None:
        """Follow a user."""
        with self._lock:
            self._following.add(user_id)
    
    def unfollow_user(self, user_id: str) -> None:
        """Unfollow a user."""
        with self._lock:
            self._following.discard(user_id)
    
    def is_following(self, user_id: str) -> bool:
        """Check if following a user."""
        with self._lock:
            return user_id in self._following
    
    def get_following(self) -> Set[str]:
        """Get set of followed users."""
        with self._lock:
            return self._following.copy()
    
    # Post management
    def add_post(self, post: Post) -> None:
        """Add a post to the feed."""
        with self._lock:
            self._post_feed.append(post)
    
    def get_posts(self, filter_followed: bool = False, user_id: Optional[str] = None) -> List[Post]:
        """Get posts, optionally filtered by followed users."""
        with self._lock:
            posts = list(self._post_feed)
            
            if filter_followed and user_id:
                # Show posts from followed users + own posts
                posts = [p for p in posts if self._should_show_post(p, user_id)]
            
            return posts
    
    def _should_show_post(self, post: Post, user_id: str) -> bool:
        """Check if post should be shown to user."""
        if post.user_id == user_id:
            return True
        
        if post.user_id in self._following:
            return True
        
        # Fallback: match by display name if user_id changed
        for followed_uid in self._following:
            peer = self._peers.get(followed_uid)
            if peer and peer.display_name == post.display_name:
                return True
        
        return False
    
    def find_post(self, user_id: str, timestamp: float) -> Optional[Post]:
        """Find a post by user and timestamp."""
        with self._lock:
            for post in self._post_feed:
                if post.user_id == user_id and post.timestamp == timestamp:
                    return post
            return None
    
    # Direct message management
    def set_local_user(self, user_id: str) -> None:
        with self._lock:
            self._local_user_id = user_id

    def add_dm(self, message: DirectMessage) -> None:
        """Store DM under the other party's user_id so a single thread shows both directions."""
        with self._lock:
            if self._local_user_id:
                if message.from_user == self._local_user_id:
                    key = message.to_user        # outgoing -> store under recipient
                elif message.to_user == self._local_user_id:
                    key = message.from_user      # incoming -> store under sender
                else:
                    key = message.from_user      # fallback
            else:
                key = message.from_user          # legacy fallback

            if key not in self._dm_history:
                self._dm_history[key] = []
            self._dm_history[key].append(message)

    
    def get_dm_history(self, user_id: str) -> List[DirectMessage]:
        """Get DM history with a user."""
        with self._lock:
            return self._dm_history.get(user_id, []).copy()
    
    def set_active_dm_user(self, user_id: Optional[str]) -> None:
        """Set the currently active DM user."""
        with self._lock:
            self._active_dm_user = user_id
    
    def get_active_dm_user(self) -> Optional[str]:
        """Get the currently active DM user."""
        with self._lock:
            return self._active_dm_user
    
    def get_dm_conversations(self) -> Dict[str, int]:
        """Get DM conversations with message counts."""
        with self._lock:
            return {uid: len(messages) for uid, messages in self._dm_history.items()}
    
    # Game management
    def add_ttt_invite(self, invite: TicTacToeInvite) -> None:
        """Add a Tic Tac Toe invite."""
        with self._lock:
            key = (invite.from_user, invite.game_id)
            self._ttt_invites[key] = invite
    
    def get_ttt_invite(self, from_user: str, game_id: str) -> Optional[TicTacToeInvite]:
        """Get a Tic Tac Toe invite."""
        with self._lock:
            return self._ttt_invites.get((from_user, game_id))
    
    def remove_ttt_invite(self, from_user: str, game_id: str) -> None:
        """Remove a Tic Tac Toe invite."""
        with self._lock:
            key = (from_user, game_id)
            self._ttt_invites.pop(key, None)
    
    def get_ttt_invites_for_user(self, user_id: str) -> List[TicTacToeInvite]:
        """Get all invites from a specific user."""
        with self._lock:
            return [invite for (from_user, _), invite in self._ttt_invites.items() 
                   if from_user == user_id]
    
    def add_ttt_game(self, game: TicTacToeGame) -> None:
        """Add a Tic Tac Toe game."""
        with self._lock:
            self._ttt_games[game.game_id] = game
    
    def get_ttt_game(self, game_id: str) -> Optional[TicTacToeGame]:
        """Get a Tic Tac Toe game."""
        with self._lock:
            return self._ttt_games.get(game_id)
    
    def remove_ttt_game(self, game_id: str) -> None:
        """Remove a Tic Tac Toe game and any pending invites that reference it."""
        with self._lock:
            # Remove the game
            self._ttt_games.pop(game_id, None)

            # Remove any invites with this game_id (keys are (from_user, game_id))
            to_delete = [k for k in self._ttt_invites.keys() if k[1] == game_id]
            for k in to_delete:
                self._ttt_invites.pop(k, None)
    
    def get_ttt_games_for_user(self, user_id: str) -> List[TicTacToeGame]:
        """Get all games involving a specific user."""
        with self._lock:
            return [game for game in self._ttt_games.values() 
                   if user_id in game.players.values()]
    
    # Group management
    def add_group(self, group: Group) -> None:
        """Add a group."""
        with self._lock:
            self._groups[group.group_id] = group
            if group.group_id not in self._group_messages:
                self._group_messages[group.group_id] = []
    
    def get_group(self, group_id: str) -> Optional[Group]:
        """Get a group by ID."""
        with self._lock:
            return self._groups.get(group_id)
    
    def get_groups_for_user(self, user_id: str) -> List[Group]:
        """Get all groups that a user is a member of."""
        with self._lock:
            return [group for group in self._groups.values() if group.is_member(user_id)]
    
    def remove_group(self, group_id: str) -> None:
        """Remove a group."""
        with self._lock:
            self._groups.pop(group_id, None)
            self._group_messages.pop(group_id, None)
    
    def update_group_membership(self, group_id: str, add_members: List[str] = None, remove_members: List[str] = None) -> bool:
        """Update group membership."""
        with self._lock:
            group = self._groups.get(group_id)
            if not group:
                return False
            
            if add_members:
                for member in add_members:
                    group.add_member(member)
            
            if remove_members:
                for member in remove_members:
                    group.remove_member(member)
            
            return True
    
    def add_group_message(self, message: GroupMessage) -> None:
        """Add a group message."""
        with self._lock:
            if message.group_id not in self._group_messages:
                self._group_messages[message.group_id] = []
            self._group_messages[message.group_id].append(message)
    
    def get_group_messages(self, group_id: str) -> List[GroupMessage]:
        """Get all messages for a group."""
        with self._lock:
            return self._group_messages.get(group_id, []).copy()
    
    def get_all_groups(self) -> List[Group]:
        """Get all groups."""
        with self._lock:
            return list(self._groups.values())
    
    def mark_ack_pending(self, message_id: str) -> threading.Event:
        """Create/register an Event for this message_id ACK."""
        evt = threading.Event()
        with self._lock:
            self._pending_acks[message_id] = evt
        return evt

    def resolve_ack(self, message_id: str) -> None:
        """Signal that ACK arrived for message_id (idempotent)."""
        with self._lock:
            evt = self._pending_acks.pop(message_id, None)
        if evt:
            evt.set()

    def wait_for_ack(self, message_id: str, timeout: float) -> bool:
        """Block up to timeout waiting for the ACK Event."""
        with self._lock:
            evt = self._pending_acks.get(message_id)
        return evt.wait(timeout) if evt else False

    def drop_ack_wait(self, message_id: str) -> None:
        """Remove pending ACK without setting it (cleanup after giving up)."""
        with self._lock:
            self._pending_acks.pop(message_id, None)
    
    def notify_incoming_file_offer(self, fileid: str, offer: dict) -> None:
        for cb in self._incoming_file_listeners:
            try:
                cb(fileid, offer)
            except Exception:
                pass

    def register_incoming_file_listener(self, callback: Callable[[str, dict], None]):
        """Callback signature: fn(fileid: str, offer: dict)"""
        self._incoming_file_listeners.append(callback)

# Global application state instance
app_state = ApplicationState()
