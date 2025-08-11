"""Message router for handling incoming messages."""
from typing import Callable, Dict
from ..network.protocol import build_message
from ..utils.dedupe import seen_before
from ..utils.auth import require_valid_token

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

class MessageRouter:
    """Routes incoming messages to appropriate handlers."""
    
    def __init__(self, network_manager: NetworkManager, verbose: bool = False):
        self.network_manager = network_manager
        self.verbose = verbose
        
        # Initialize handlers
        self.handlers = {
            "PING": PingHandler(verbose=verbose).handle,
            "PROFILE": ProfileHandler(verbose=verbose).handle,
            "DM": DmHandler(network_manager, verbose=verbose).handle,
            "POST": PostHandler(verbose=verbose).handle,
            "LIKE": LikeHandler(verbose=verbose).handle,
            "TICTACTOE_INVITE": GameHandler(network_manager, verbose=verbose).handle_invite,
            "TICTACTOE_MOVE": GameHandler(network_manager, verbose=verbose).handle_move,
            "TICTACTOE_RESULT": GameHandler(network_manager, verbose=verbose).handle_result,
            "GROUP_CREATE": GroupHandler(network_manager, verbose=verbose).handle_create,
            "GROUP_UPDATE": GroupHandler(network_manager, verbose=verbose).handle_update,
            "GROUP_MESSAGE": GroupHandler(network_manager, verbose=verbose).handle_message,
            "FILE_OFFER": handle_file_message,
            "FILE_CHUNK": handle_file_message,
            "FILE_RECEIVED": handle_file_message,
        }
    
    def route_message(self, msg: dict, addr: tuple) -> None:
        """Route incoming messages to appropriate handlers."""
        mtype = msg.get("TYPE", "")
        
        # Handle ACKs immediately before any other processing
        if mtype == "ACK":
            self._handle_ack(msg, addr)
            return

        # Global message deduplication
        message_id = msg.get("MESSAGE_ID")
        if message_id and seen_before(message_id):
            if self.verbose:
                print(f"[ROUTER] Dropping duplicate message {message_id}")
            return
            
        # Validate token if required
        if not require_valid_token(msg, addr, self.verbose):
            return

        # Route to appropriate handler
        if mtype in self.handlers:
            try:
                self.handlers[mtype](msg, addr)
            except Exception as e:
                if self.verbose:
                    print(f"[ROUTER] Error handling {mtype}: {e}")
        elif self.verbose:
            print(f"[ROUTER] Unhandled message type: {mtype}")

    def _handle_ack(self, msg: dict, addr: tuple) -> None:
        """Handle incoming ACK messages."""
        mid = msg.get("MESSAGE_ID")
        if not mid:
            return
            
        if self.verbose:
            print(f"[ACK] Processing ACK for message {mid} from {addr[0]}")
            
        app_state.acknowledge(mid)