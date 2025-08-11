"""Handler for DM messages."""
from ..models.user import DirectMessage, Peer
from ..network.client import NetworkManager
from ..core.state import app_state
from ..utils.dedupe import seen_before

class DmHandler:
    """Handles DM messages."""
    
    def __init__(self, network_manager: NetworkManager, verbose: bool = False):
        self.network_manager = network_manager
        self.verbose = verbose
    
    def handle(self, msg: dict, addr: tuple) -> None:
        """Handle a DM message."""
        # Add message deduplication
        message_id = msg.get("MESSAGE_ID")
        if message_id and seen_before(message_id):
            if self.verbose:
                print(f"[DM] Dropping duplicate message {message_id}")
            return

        from_user = msg.get("FROM")
        to_user = msg.get("TO")
        content = msg.get("CONTENT", "")
        timestamp = float(msg.get("TIMESTAMP", 0))
        
        if self.verbose:
            print(f"[DEBUG] DM parsed - From: '{from_user}', To: '{to_user}', Content: '{content}'")

        if not from_user or not content:
            if self.verbose:
                print(f"[DEBUG] Invalid DM - missing FROM or CONTENT")
            return

        # Update sender's IP
        app_state.update_peer_ip(from_user, addr[0])

        # Get display name
        peer = app_state.get_peer(from_user)
        sender_display = peer.display_name if peer else (
            from_user.split("@")[0] if "@" in from_user else from_user
        )

        # Create DM object
        dm = DirectMessage(
            from_user=from_user,
            to_user=to_user or "",
            content=content,
            timestamp=timestamp,
            message_id=message_id,
            display_name=sender_display
        )
        
        # Add to history
        app_state.add_dm(dm)

        # Display message
        active_dm_user = app_state.get_active_dm_user()
        if active_dm_user == from_user:
            print(f"\n💬 {sender_display}: {content}")
            print(f"[You → {sender_display}]: ", end="", flush=True)
        else:
            print(f"\n💬 New message from {sender_display}: {content}")
            print("> ", end="", flush=True)

        # Send ACK if message has ID
        if message_id:
            self.network_manager.send_ack(message_id, addr)