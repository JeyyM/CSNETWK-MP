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
from ..utils.dedupe import seen_before

class MessageRouter:
    """Routes incoming messages to appropriate handlers."""
    
    def __init__(self, network_manager: NetworkManager, verbose: bool = False):
        self.verbose = verbose
        
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
        }
    
    def route_message(self, msg: dict, addr: tuple) -> None:
        message_type = msg.get("TYPE", "")
        
        if message_type.startswith("FILE_"):
            handle_file_message(msg, addr)
            return
        
        handler = self.handlers.get(message_type)
        if handler:
            handler(msg, addr)
        else:
            if self.verbose:
                print(f"⚠️ Unknown message type: {message_type}")

    
    def _handle_ack(self, msg: dict, addr: tuple) -> None:
        """Handle ACK messages."""
        if self.verbose:
            print(f"✅ ACK received from {addr}")
