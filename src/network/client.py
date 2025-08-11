"""Network communication utilities."""
import socket
import re
import time
from typing import Optional

from .protocol import build_message
from ..core.state import app_state
from .protocol import parse_message

PORT = 50999


def get_local_ip() -> str:
    """Get the local IP address."""
    try:
        temp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_sock.connect(("8.8.8.8", 80))
        ip = temp_sock.getsockname()[0]
        temp_sock.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_broadcast_ip() -> str:
    """Automatically determine broadcast address based on local IP."""
    try:
        local_ip = get_local_ip()
        parts = local_ip.split(".")
        parts[-1] = "255"
        return ".".join(parts)
    except Exception:
        return "255.255.255.255"


def extract_ip_from_user_id(user_id: str) -> Optional[str]:
    """Extract IPv4 address from user_id format (username@ip)."""
    if "@" not in user_id:
        return None
    ip = user_id.split("@", 1)[1].strip()
    return ip if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip) else None


class NetworkManager:
    """Manages network communication."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
    
    def _auto_register_token(self, message: str) -> None:
        """Parse outgoing message and remember its TOKEN for later revoke."""
        try:
            fields = parse_message(message)
            tok = fields.get("TOKEN")
            if tok:
                app_state.register_issued_token(tok)
        except Exception:
            pass
    
    def send_unicast(self, message: str, user_id: str) -> bool:
        """Send a unicast message to a specific user."""
        ip = app_state.get_peer_ip(user_id)
        if not ip:
            ip = extract_ip_from_user_id(user_id)
            if self.verbose and ip:
                print("\n\nvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv\n\n" + message + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n")
                print(f"[DEBUG] Using IP parsed from UID ({user_id}) -> {ip}")
        
        if not ip:
            if self.verbose:
                print("\n\nvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv\n\n" + message + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n")
                print(f"[DEBUG] No IP mapping and no @IP in UID for {user_id}")
            return False

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self._auto_register_token(message)
            sock.sendto(message.encode("utf-8"), (ip, PORT))
            return True
        except Exception as e:
            print(f"Failed to send to {user_id} ({ip}): {e}")
            return False
        finally:
            sock.close()
    
    def send_broadcast(self, message: str) -> None:
        """Send a broadcast message."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
        # Try both subnet and limited broadcast
        broadcast_addresses = {get_broadcast_ip(), "255.255.255.255"}
        
        for bcast in broadcast_addresses:
            try:
                self._auto_register_token(message)
                sock.sendto(message.encode("utf-8"), (bcast, PORT))
            except Exception as e:
                print(f"Broadcast to {bcast} failed: {e}")
        
        sock.close()
    
    def send_ack(self, message_id: str, addr: tuple) -> None:
        """
        Send an ACK for message_id back to the peer's *listening* LSNP port.
        NOTE: We intentionally ignore the peer's ephemeral source port (addr[1]).
        """
        if not message_id:
            return

        ack_fields = {
            "TYPE": "ACK",
            "MESSAGE_ID": message_id,
            "STATUS": "RECEIVED",
        }
        ack_msg = build_message(ack_fields)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Force destination to (peer_ip, 50999) instead of the source port.
            sock.sendto(ack_msg.encode("utf-8"), (addr[0], PORT))
            if self.verbose:
                print("\n\nvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv\n\n" + ack_msg + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n")
                print(f"Sent ACK for {message_id} to {addr}")
        except Exception as e:
            if self.verbose:
                print(f"Failed to send ACK: {e}")
        finally:
            sock.close()