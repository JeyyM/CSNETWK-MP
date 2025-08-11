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
                    file_types = (
                        'FILE_OFFER', 'FILE_CHUNK', 'FILE_RECEIVED', 'FILE_ACCEPT', 'FILE_REJECT'
                    )
                    msg_type = msg.get('TYPE', '?')
                    if msg_type in file_types:
                        # Print detailed file message
                        print(f"TYPE: {msg_type}")
                        for k in [
                            "FROM", "TO", "FILENAME", "FILESIZE", "FILETYPE", "FILEID", "DESCRIPTION",
                            "TIMESTAMP", "TOKEN", "TOTAL_CHUNKS", "CHUNK_SIZE", "CHUNK_INDEX", "DATA",
                            "STATUS", "MESSAGE_ID"
                        ]:
                            if k in msg and msg[k] != "":
                                # For DATA, print only a short preview
                                if k == "DATA":
                                    data_val = msg[k]
                                    preview = data_val[:32] + ("..." if len(data_val) > 32 else "")
                                    print(f"{k}: {preview}")
                                else:
                                    print(f"{k}: {msg[k]}")
                        print()
                    # Only show old verbose for non-PING, non-PROFILE, non-POST, non-DM, non-file messages
                    elif msg_type not in ('PING', 'PROFILE', 'POST', 'DM'):
                        print(f"\nRECV< {t} {addr[0]}:{addr[1]} TYPE={msg_type}")

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
