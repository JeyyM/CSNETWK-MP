"""Message router for handling incoming messages."""
from typing import Callable, Dict

from .ping_handler import PingHandler
from .profile_handler import ProfileHandler
from .dm_handler import DmHandler
from .post_handler import PostHandler
from .like_handler import LikeHandler
from .game_handler import GameHandler
from .group_handler import GroupHandler
from ..network.client import NetworkManager
from ..handlers.file_handler import handle_file_message

from ..core.state import app_state
from ..utils.auth import require_valid_token

class MessageRouter:
    """Routes incoming messages to appropriate handlers."""
    
    def __init__(self, network_manager: NetworkManager, verbose: bool = False):
        self.verbose = verbose
        self.network_manager = network_manager 
        
        # Initialize handlers
        self.ping_handler = PingHandler(verbose)
        self.profile_handler = ProfileHandler(verbose)
        self.dm_handler = DmHandler(network_manager, verbose)
        self.post_handler = PostHandler(verbose)
        self.like_handler = LikeHandler(verbose)
        self.game_handler = GameHandler(network_manager, verbose)
        self.group_handler = GroupHandler(network_manager, verbose)
        
        # Message type routing table
        self.handlers: Dict[str, Callable[[dict, tuple], None]] = {
            "PING": self.ping_handler.handle,
            "PROFILE": self.profile_handler.handle,
            "DM": self.dm_handler.handle,
            "POST": self.post_handler.handle,
            "LIKE": self.like_handler.handle,
            "TICTACTOE_INVITE": self.game_handler.handle_invite,
            "TICTACTOE_MOVE": self.game_handler.handle_move,
            "TICTACTOE_RESULT": self.game_handler.handle_result,
            "GROUP_CREATE": self.group_handler.handle_group_create,
            "GROUP_UPDATE": self.group_handler.handle_group_update,
            "GROUP_MESSAGE": self.group_handler.handle_group_message,
            "ACK": self._handle_ack,

            "FILE_OFFER": handle_file_message,
            "FILE_ACCEPT": handle_file_message,
            "FILE_REJECT": handle_file_message,
            "FILE_CHUNK": handle_file_message,
            "FILE_RECEIVED": handle_file_message,
            
            "REVOKE": self._handle_revoke
        }

        self.ack_types = {"DM", "TICTACTOE_INVITE", "TICTACTOE_MOVE",
            "FILE_OFFER", "FILE_CHUNK"}
    
    def route_message(self, msg: dict, addr: tuple) -> None:
        """Route incoming messages to appropriate handlers."""
        mtype = msg.get("TYPE", "")

        # Handle ACKs immediately before any other processing
        if mtype == "ACK":
            self._handle_ack(msg, addr)
            return

        # Validate token if present (except for ACK which was handled above)
        token = msg.get("TOKEN")
        if token:
            valid, reason = app_state.validate_token(token, "game")
            if not valid:
                if self.verbose:
                    print(f"[AUTH] Invalid token: {reason}")
                return

        # Route to appropriate handler
        if mtype in self.handlers:
            self.handlers[mtype](msg, addr)
        elif self.verbose:
            print(f"[ROUTER] Unhandled message type: {mtype}")

    def _handle_ack(self, msg: dict, addr: tuple) -> None:
        """Handle incoming ACK messages."""
        mid = msg.get("MESSAGE_ID")
        if not mid:
            return
            
        if self.verbose:
            print(f"[ACK] Received ACK for {mid} from {addr[0]}")
            
        app_state.acknowledge(mid)

    
    def _handle_ack(self, msg: dict, addr: tuple) -> None:
        mid = msg.get("MESSAGE_ID")
        if mid:
            app_state.resolve_ack(mid)
            if self.verbose:
                print(f"[ACK] Received ACK for {mid} from {addr[0]}:{addr[1]}")
        elif self.verbose:
            print(f"[ACK] Received ACK without MESSAGE_ID from {addr[0]}:{addr[1]}")

    def _handle_revoke(self, msg: dict, addr: tuple) -> None:
        tok = msg.get("TOKEN")
        if not tok:
            if self.verbose:
                print("[REVOKE] Missing TOKEN")
            return

        parsed = app_state.parse_token(tok)
        if not parsed:
            if self.verbose:
                print("[REVOKE] Malformed token string in REVOKE")
            return

        user_id, expiry, scope = parsed

        # Mark token revoked locally
        app_state.revoke_token(tok)

        # Remove the peer entirely from the active list
        app_state.remove_peer(user_id)

        if self.verbose:
            print(f"[REVOKE] From {user_id} (scope={scope}). Removed from active list.")
