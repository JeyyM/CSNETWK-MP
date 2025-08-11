"""Central application state management."""
from typing import Dict, List, Set, Optional, Callable
from threading import Lock
import time

from ..models.user import Peer, DirectMessage, Post
from ..models.game import TicTacToeInvite, TicTacToeGame


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

        # File offer listeners (UI callbacks)
        # Callback signature: fn(fileid: str, offer: dict)
        self._incoming_file_listeners: List[Callable[[str, dict], None]] = []
    
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
    
    def get_active_peers(self, exclude_user_id: Optional[str] = None) -> List[Peer]:
        """Get all active peers."""
        with self._lock:
            peers = [p for p in self._peers.values() if p.is_active]
            if exclude_user_id:
                peers = [p for p in peers if p.user_id != exclude_user_id]
            return peers
    
    def get_peer_ip(self, user_id: str) -> Optional[str]:
        """Get IP address for a user."""
        with self._lock:
            return self._user_ip_map.get(user_id)
    
    def update_peer_ip(self, user_id: str, ip: str) -> None:
        """Update IP address for a user."""
        with self._lock:
            self._user_ip_map[user_id] = ip
    
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
    def add_dm(self, message: DirectMessage) -> None:
        """Add a direct message."""
        with self._lock:
            if message.from_user not in self._dm_history:
                self._dm_history[message.from_user] = []
            self._dm_history[message.from_user].append(message)
    
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
        """Remove a Tic Tac Toe game."""
        with self._lock:
            self._ttt_games.pop(game_id, None)
    
    def get_ttt_games_for_user(self, user_id: str) -> List[TicTacToeGame]:
        """Get all games involving a specific user."""
        with self._lock:
            return [game for game in self._ttt_games.values() 
                   if user_id in game.players.values()]
    
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
