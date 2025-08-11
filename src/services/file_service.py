# src/services/file_service.py
import os
import math
import base64
import uuid
import time
import threading
from typing import Dict, Optional

from ..network.client import NetworkManager, extract_ip_from_user_id
from ..network.protocol import build_message
from ..core.state import app_state
from ..models.user import User

DEFAULT_CHUNK_SIZE = 1024
SEND_RETRY_DELAY = 0.2
OFFER_TIMEOUT = 30  # seconds


class FileService:
    def __init__(self, network_manager: NetworkManager, user: User, verbose: bool = False):
        self.network = network_manager
        self.user = user
        self.verbose = verbose

        # Outgoing offers keyed by fileid
        self.outgoing: Dict[str, dict] = {}
        # Pending incoming offers (not yet accepted) keyed by fileid
        self.incoming_offers: Dict[str, dict] = {}
        # Active incoming transfers: fileid -> {filename,total_chunks,chunks,from}
        self.incoming_active: Dict[str, dict] = {}

    # ---------------- Sender side ----------------
    def offer_file(self, to_uid: str, file_path: str, description: str = "") -> Optional[str]:
        if not os.path.isfile(file_path):
            print(f"File not found: {file_path}")
            return None

        if to_uid == self.user.user_id:
            print("Cannot send file to yourself.")
            return None

        filesize = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        fileid = uuid.uuid4().hex[:8]
        ts = int(time.time())
        token = f"{self.user.user_id}|{ts+3600}|file"

        total_chunks = max(1, math.ceil(filesize / DEFAULT_CHUNK_SIZE))

        fields = {
            "TYPE": "FILE_OFFER",
            "FROM": self.user.user_id,
            "TO": to_uid,
            "FILENAME": filename,
            "FILESIZE": str(filesize),
            "FILETYPE": "application/octet-stream",
            "FILEID": fileid,
            "DESCRIPTION": description,
            "TIMESTAMP": str(ts),
            "TOKEN": token,
            "TOTAL_CHUNKS": str(total_chunks),
            "CHUNK_SIZE": str(DEFAULT_CHUNK_SIZE),
            "MESSAGE_ID": uuid.uuid4().hex[:8],
        }

        # Do NOT broadcast file offers; only send unicast to the recipient
        sent = self.network.send_unicast(build_message(fields), to_uid)
        if not sent:
            print("Failed to send FILE_OFFER.")
            return None

        self.outgoing[fileid] = {
            "to": to_uid,
            "path": file_path,
            "filename": filename,
            "size": filesize,
            "total_chunks": total_chunks,
            "token": token,
            "state": "offered",
            "offer_time": ts,
            "accept_event": threading.Event(),
        }

        # Start watcher thread for accept timeout + eventual send
        t = threading.Thread(target=self._wait_for_accept_then_send, args=(fileid,), daemon=True)
        t.start()

        return fileid

    def _wait_for_accept_then_send(self, fileid: str) -> None:
        meta = self.outgoing.get(fileid)
        if not meta:
            return
        accepted = meta["accept_event"].wait(timeout=OFFER_TIMEOUT)
        if not accepted:
            meta["state"] = "timed_out"
            print(f"Offer {fileid} timed out (no accept).")
            self.outgoing.pop(fileid, None)
            return
        meta["state"] = "sending"
        t = threading.Thread(target=self._send_chunks, args=(fileid,), daemon=True)
        t.start()

    def _send_chunks(self, fileid: str) -> None:
        meta = self.outgoing.get(fileid)
        if not meta:
            return
        to_uid = meta["to"]
        path = meta["path"]
        chunk_size = DEFAULT_CHUNK_SIZE
        total = meta["total_chunks"]
        idx = 0

        if to_uid == self.user.user_id:
            print("Not sending file chunks to yourself.")
            return

        try:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    data_b64 = base64.b64encode(chunk).decode("utf-8")
                    fields = {
                        "TYPE": "FILE_CHUNK",
                        "FROM": self.user.user_id,
                        "TO": to_uid,
                        "FILEID": fileid,
                        "CHUNK_INDEX": str(idx),
                        "TOTAL_CHUNKS": str(total),
                        "CHUNK_SIZE": str(len(chunk)),
                        "DATA": data_b64,
                        "TOKEN": meta["token"],
                        "MESSAGE_ID": uuid.uuid4().hex[:8],
                        "TIMESTAMP": str(int(time.time())),
                    }

                    # Do NOT broadcast file chunks; only send unicast to the recipient
                    sent = self.network.send_unicast(build_message(fields), to_uid)
                    if not sent:
                        # retry once
                        time.sleep(SEND_RETRY_DELAY)
                        self.network.send_unicast(build_message(fields), to_uid)
                    idx += 1
                    time.sleep(0.01)
        except Exception as e:
            print(f"Error while sending chunks for {fileid}: {e}")
            self.outgoing.pop(fileid, None)
            return

        print(f"Finished sending file {meta['filename']} -> {to_uid}")
        meta["state"] = "sent"

    def handle_file_accept(self, msg: dict, addr: tuple) -> None:
        fileid = msg.get("FILEID")
        # Ignore FILE_ACCEPT from self
        if msg.get("FROM") == self.user.user_id:
            return
        meta = self.outgoing.get(fileid)
        if not meta:
            # Silently ignore unknown fileid from other users
            return
        meta["accept_event"].set()
        print(f"[FILE] Offer {fileid} accepted by {meta['to']} - starting transfer")

    def handle_file_received(self, msg: dict, addr: tuple) -> None:
        fileid = msg.get("FILEID")
        status = msg.get("STATUS", "")
        meta = self.outgoing.pop(fileid, None)
        if meta:
            to_uid = meta["to"]

            fields = {
                "TYPE": "FILE_RECEIVED",
                "FROM": self.user.user_id,
                "TO": to_uid,
                "FILEID": fileid,
                "STATUS": "COMPLETE",
                "TIMESTAMP": str(int(time.time())),
            }
            file_chunk_msg = build_message(fields)

            self.network.send_broadcast(file_chunk_msg)

    # ---------------- Receiver side ----------------
    def handle_file_offer_incoming(self, msg: dict, addr: tuple) -> None:
        fileid = msg.get("FILEID")
        if not fileid:
            return
        offer = {
            "from": msg.get("FROM"),
            "to": msg.get("TO"),
            "filename": msg.get("FILENAME"),
            "filesize": int(msg.get("FILESIZE", "0")),
            "filetype": msg.get("FILETYPE"),
            "description": msg.get("DESCRIPTION", ""),
            "token": msg.get("TOKEN"),
            "total_chunks": int(msg.get("TOTAL_CHUNKS", "0")),
            "chunk_size": int(msg.get("CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE))),
            "timestamp": int(msg.get("TIMESTAMP", str(int(time.time())))),
            "message_id": msg.get("MESSAGE_ID"),
        }
        self.incoming_offers[fileid] = offer
        # notify UI
        app_state.notify_incoming_file_offer(fileid, offer)

    def accept_offer(self, fileid: str) -> bool:
        offer = self.incoming_offers.get(fileid)
        if not offer:
            print("No such offer.")
            return False
        sender = offer["from"]
        ts = int(time.time())
        fields = {
            "TYPE": "FILE_ACCEPT",
            "FROM": self.user.user_id,
            "TO": sender,
            "FILEID": fileid,
            "TIMESTAMP": str(ts),
            "MESSAGE_ID": uuid.uuid4().hex[:8],
        }
        sent = self.network.send_unicast(build_message(fields), sender)
        if sent:
            self.incoming_active[fileid] = {
                "filename": offer["filename"],
                "size": offer["filesize"],
                "total_chunks": offer["total_chunks"],
                "chunks": {},
                "from": sender,
                "received_time": int(time.time()),
            }
            self.incoming_offers.pop(fileid, None)
            return True
        print("Failed to send FILE_ACCEPT.")
        return False

    def reject_offer(self, fileid: str) -> bool:
        offer = self.incoming_offers.pop(fileid, None)
        if not offer:
            print("No such offer.")
            return False
        sender = offer["from"]
        ts = int(time.time())
        fields = {
            "TYPE": "FILE_REJECT",
            "FROM": self.user.user_id,
            "TO": sender,
            "FILEID": fileid,
            "TIMESTAMP": str(ts),
            "MESSAGE_ID": uuid.uuid4().hex[:8],
        }
        sent = self.network.send_unicast(build_message(fields), sender)
        return bool(sent)

    def handle_file_chunk_incoming(self, msg: dict, addr: tuple) -> None:
        fileid = msg.get("FILEID")
        if fileid not in self.incoming_active:
            print(f"[FILE] Ignoring chunk for unknown/unaccepted fileid {fileid}")
            return
        try:
            idx = int(msg.get("CHUNK_INDEX"))
        except Exception:
            return
        data_b64 = msg.get("DATA")
        if data_b64 is None:
            return
        try:
            chunk = base64.b64decode(data_b64)
        except Exception:
            return

        rec = self.incoming_active[fileid]
        rec["chunks"][idx] = chunk
        if len(rec["chunks"]) == rec["total_chunks"]:
            self._assemble_incoming(fileid)

    def _assemble_incoming(self, fileid: str) -> None:
        rec = self.incoming_active.pop(fileid, None)
        if not rec:
            return
        downloads = os.path.join(os.getcwd(), "downloads")
        os.makedirs(downloads, exist_ok=True)
        out_name = f"{int(time.time())}_{rec['filename']}"
        out_path = os.path.join(downloads, out_name)
        try:
            with open(out_path, "wb") as f:
                for i in range(rec["total_chunks"]):
                    f.write(rec["chunks"][i])
        except Exception as e:
            print(f"Failed to assemble file {rec['filename']}: {e}")
            return

        print(f"\nReceived file: {out_path}")
        # send FILE_RECEIVED back
        fields = {
            "TYPE": "FILE_RECEIVED",
            "FROM": self.user.user_id,
            "TO": rec["from"],
            "FILEID": fileid,
            "STATUS": "COMPLETE",
            "TIMESTAMP": str(int(time.time())),
            "MESSAGE_ID": uuid.uuid4().hex[:8],
        }
        self.network.send_unicast(build_message(fields), rec["from"])
        # send FILE_RECEIVED back
        fields = {
            "TYPE": "FILE_RECEIVED",
            "FROM": self.user.user_id,
            "TO": rec["from"],
            "FILEID": fileid,
            "STATUS": "COMPLETE",
            "TIMESTAMP": str(int(time.time())),
            "MESSAGE_ID": uuid.uuid4().hex[:8],
        }
        self.network.send_unicast(build_message(fields), rec["from"])
