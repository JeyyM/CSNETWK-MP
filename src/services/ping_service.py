"""Ping service for network discovery."""
import time
from threading import Thread

from ..models.user import User
from ..network.client import NetworkManager
from ..network.protocol import build_message


class PingService:
    """Service for network discovery via ping."""
    
    def __init__(self, network_manager: NetworkManager):
        self.network_manager = network_manager
        self._ping_thread = None
        self._profile_thread = None
        self._running = False
    
    def start_ping_service(self, user: User, ping_interval: int = 300, profile_interval: int = 300) -> None:
        """Start periodic ping and profile broadcasting."""
        self._running = True
        
        # Start ping thread
        self._ping_thread = Thread(
            target=self._ping_loop,
            args=(user, ping_interval),
            daemon=True
        )
        self._ping_thread.start()
        
        # Start profile broadcast thread
        self._profile_thread = Thread(
            target=self._profile_loop,
            args=(user, profile_interval),
            daemon=True
        )
        self._profile_thread.start()
    
    def stop_ping_service(self) -> None:
        """Stop the ping service."""
        self._running = False
    
    def _ping_loop(self, user: User, interval: int) -> None:
        """Ping loop thread."""
        while self._running:
            self._send_ping(user)
            time.sleep(interval)
    
    def _profile_loop(self, user: User, interval: int) -> None:
        """Profile broadcast loop thread."""
        while self._running:
            self._send_profile(user)
            time.sleep(interval)
    
    def _send_ping(self, user: User) -> None:
        """Send a ping message."""
        fields = {
            "TYPE": "PING",
            "USER_ID": user.user_id
        }
        ping_msg = build_message(fields)
        self.network_manager.send_broadcast(ping_msg)
        
    def _send_profile(self, user: User) -> None:
        """Send a profile broadcast."""
        fields = {
            "TYPE": "PROFILE",
            "USER_ID": user.user_id,
            "DISPLAY_NAME": user.display_name,
            "STATUS": user.status,
        }
        profile_msg = build_message(fields)

        self.network_manager.send_broadcast(profile_msg)
        # print("\n\n====================================================================\n\n" + profile_msg + "====================================================================\n\n")
        
        if user.verbose:
            print(f"[PROFILE] Sent profile broadcast")
        
        if user.verbose:
            print(f"[PROFILE] Sent profile broadcast")
