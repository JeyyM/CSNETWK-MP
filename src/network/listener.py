"""UDP listener for incoming messages."""
import socket
import time
from typing import Callable

from .protocol import parse_message


PORT = 50999
BUFFER_SIZE = 65535
LISTEN_IP = ''


class UDPListener:
    """UDP message listener."""
    
    def __init__(self, message_router: Callable[[dict, tuple], None], verbose: bool = False):
        self.message_router = message_router
        self.verbose = verbose
        self.running = False
    
    def start(self) -> None:
        """Start the UDP listener."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # receive broadcasts

        # Bind with simple retry
        for retry in range(5):
            try:
                sock.bind((LISTEN_IP, PORT))
                break
            except OSError as e:
                if retry == 4:
                    print(f"Failed to bind to port {PORT} after 5 attempts: {e}")
                    return
                print(f"Retry {retry + 1}: Failed to bind to port {PORT}, retrying in 1 second...")
                time.sleep(1)

        print(f"Listening on UDP port {PORT}")
        self.running = True

        try:
            while self.running:
                try:
                    data, addr = sock.recvfrom(BUFFER_SIZE)
                    raw = data.decode("utf-8", errors="ignore")
                except Exception as e:
                    if self.verbose:
                        print(f"Receive error: {e}")
                    continue

                msg = parse_message(raw)
                if not msg:
                    if self.verbose:
                        print(f"DROP! Invalid or unterminated message from {addr}.")
                    continue

                if self.verbose:
                    t = time.strftime("%H:%M:%S")
                    # Only show verbose for non-PING, non-PROFILE, non-POST, non-DM messages
                    if msg.get('TYPE', '?') not in ('PING', 'PROFILE', 'POST', 'DM'):
                        print(f"\nRECV< {t} {addr[0]}:{addr[1]} TYPE={msg.get('TYPE','?')}")

                # Route message to appropriate handler
                self.message_router(msg, addr)

        except KeyboardInterrupt:
            print("\n[INFO] Listener stopped.")
        finally:
            self.running = False
            sock.close()
    
    def stop(self) -> None:
        """Stop the listener."""
        self.running = False
