# services/file_service.py
import os
import math
import base64
import uuid
import time
import threading
from typing import Dict, Optional

from ..network.client import NetworkManager
from ..core import state as core_state  # app_state lives here
from ..network.protocol import build_message

DEFAULT_CHUNK_SIZE = 1024
SEND_RETRY_DELAY = 0.2
OFFER_TIMEOUT = 30  # seconds to wait for accept before giving up


class FileService:
    """
    Responsible for sending file offers, streaming chunks after accept,
    and tracking outgoing & incoming transfers.
    """

    def __init__(self, network_manager: NetworkManager, user):
        self.network = network_manager
        self.user = user
        # outgoing: fileid -> metadata
        self.outgoing: Dict[str, dict] = {}
        # incoming pending offers: fileid -> metadata
        self.incoming_offers: Dict[str, dict] = {}
        # active incoming transfers storing chunks: fileid -> {'chunks':{}, 'total':int, 'filename':...}
        self.incoming_active: Dict[str, dict] = {}

    # -------------------- Sender API --------------------
    def offer_file(self, to_uid: str, file_path: str, description: str = "") -> Optional[str]:
        """Send a FILE_OFFER to recipient. Returns fileid or None on error."""
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None

        filesize = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        fileid = uuid.uuid4().hex[:8]
        ts = int(time.time())
        token = f"{self.user.user_id}|{ts+3600}|file"

        total_chunks = math.ceil(filesize / DEFAULT_CHUNK_SIZE) if filesize > 0 else 1

        fields = {
            "TYPE": "FILE_OFFER",
            "FROM": self.user.user_id,
            "TO": to_uid,
            "FILENAME": filename,
            "FILESIZE": str(filesize),
            "FILETYPE": "application/octet-stream",  # could use mimetypes
            "FILEID": fileid,
            "DESCRIPTION": description,
            "TIMESTAMP": str(ts),
            "TOKEN": token,
            "TOTAL_CHUNKS": str(total_chunks),
            "CHUNK_SIZE": str(DEFAULT_CHUNK_SIZE),
            "MESSAGE_ID": uuid.uuid4().hex[:8],
        }

        ok = self.network.send_unicast(build_message(fields), to_uid)
        if not ok:
            print("❌ Failed to send FILE_OFFER.")
            return None

        # record outgoing transfer, wait for accept
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

        # start a watcher thread to timeout if no accept
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
            print(f"⚠️ Offer {fileid} timed out (no accept).")
            # cleanup
            self.outgoing.pop(fileid, None)
            return
        # accepted -> start chunk sender
        meta["state"] = "sending"
        t = threading.Thread(target=self._send_chunks, args=(fileid,), daemon=True)
        t.start()

    def _send_chunks(self, fileid: str) -> None:
        meta = self.outgoing.get(fileid)
        if not meta:
            return
        to_uid = meta["to"]
        to_ip = core_state.app_state.get_peer_ip(to_uid)
        if not to_ip:
            to_ip = self.network.extract_ip_from_user_id(to_uid) if hasattr(self.network, "extract_ip_from_user_id") else None
        if not to_ip:
            print(f"❌ Unknown IP for {to_uid}, aborting send.")
            self.outgoing.pop(fileid, None)
            return

        path = meta["path"]
        chunk_size = int(meta.get("chunk_size", DEFAULT_CHUNK_SIZE))
        total = meta["total_chunks"]
        idx = 0
        try:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    b64 = base64.b64encode(chunk).decode("utf-8")
                    fields = {
                        "TYPE": "FILE_CHUNK",
                        "FROM": self.user.user_id,
                        "TO": to_uid,
                        "FILEID": fileid,
                        "CHUNK_INDEX": str(idx),
                        "TOTAL_CHUNKS": str(total),
                        "CHUNK_SIZE": str(len(chunk)),
                        "DATA": b64,
                        "TOKEN": meta["token"],
                        "MESSAGE_ID": uuid.uuid4().hex[:8],
                        "TIMESTAMP": str(int(time.time())),
                    }
                    sent = self.network.send_unicast(build_message(fields), to_uid)
                    if not sent:
                        # retry once
                        time.sleep(SEND_RETRY_DELAY)
                        self.network.send_unicast(build_message(fields), to_uid)
                    idx += 1
                    time.sleep(0.01)
        except Exception as e:
            print(f"❌ Error sending chunks for {fileid}: {e}")
            self.outgoing.pop(fileid, None)
            return

        print(f"📤 Finished sending file {meta['filename']} -> {to_uid}")
        # keep record until FILE_RECEIVED arrives or timeout
        meta["state"] = "sent"

    # Called by MessageRouter when a FILE_ACCEPT arrives for a fileid we offered
    def handle_file_accept(self, msg: dict, addr: tuple) -> None:
        fileid = msg.get("FILEID")
        from_uid = msg.get("FROM")  # this will be us in RFC format? rely on matching fileid
        # mark accept on outgoing
        meta = self.outgoing.get(fileid)
        if not meta:
            if self.user.verbose:
                print(f"[FILE] ACCEPT for unknown fileid {fileid}")
            return
        meta["accept_event"].set()
        if self.user.verbose:
            print(f"[FILE] Offer {fileid} accepted by {meta['to']} — starting transfer")

    # Called when sender gets FILE_RECEIVED ack (final)
    def handle_file_received(self, msg: dict, addr: tuple) -> None:
        fileid = msg.get("FILEID")
        status = msg.get("STATUS", "")
        meta = self.outgoing.get(fileid)
        if not meta:
            return
        print(f"✅ Remote acknowledged file {fileid}: {status}")
        # cleanup
        self.outgoing.pop(fileid, None)

    # -------------------- Receiver API --------------------
    def handle_file_offer_incoming(self, msg: dict, addr: tuple) -> None:
        """
        Called by MessageRouter on incoming FILE_OFFER.
        We store the offer in incoming_offers and notify UI via app_state.
        """
        fileid = msg.get("FILEID") or msg.get("TOKEN")
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
        # notify application state / UI that there's a pending offer
        core_state.app_state.notify_incoming_file_offer(fileid, offer)

    def accept_offer(self, fileid: str) -> bool:
        """User accepts an incoming file offer (UI calls this). Sends FILE_ACCEPT to sender."""
        offer = self.incoming_offers.get(fileid)
        if not offer:
            print("❌ No such offer.")
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
            # create incoming_active record to collect chunks
            self.incoming_active[fileid] = {
                "filename": offer["filename"],
                "size": offer["filesize"],
                "total_chunks": offer["total_chunks"],
                "chunks": {},
                "from": sender,
                "received_time": int(time.time()),
            }
            # remove from pending offers
            self.incoming_offers.pop(fileid, None)
            return True
        else:
            print("❌ Failed to send FILE_ACCEPT.")
            return False

    def reject_offer(self, fileid: str) -> bool:
        offer = self.incoming_offers.get(fileid)
        if not offer:
            print("❌ No such offer.")
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
        # cleanup
        self.incoming_offers.pop(fileid, None)
        return bool(sent)

    def handle_file_chunk_incoming(self, msg: dict, addr: tuple) -> None:
        """Store chunks as they arrive; assemble when complete and send FILE_RECEIVED."""
        fileid = msg.get("FILEID")
        if fileid not in self.incoming_active:
            # not accepted (or we rejected) — ignore
            if self.user.verbose:
                print(f"[FILE] Ignoring chunk for unknown or unaccepted fileid {fileid}")
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

        record = self.incoming_active[fileid]
        record["chunks"][idx] = chunk
        if len(record["chunks"]) == record["total_chunks"]:
            # assemble
            self._assemble_incoming(fileid)

    def _assemble_incoming(self, fileid: str) -> None:
        rec = self.incoming_active.get(fileid)
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
            print(f"❌ Failed to assemble file {rec['filename']}: {e}")
            self.incoming_active.pop(fileid, None)
            return

        print(f"✅ Received file: {out_path}")
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
        # cleanup
        self.incoming_active.pop(fileid, None)
