# file_client.py
import os
import math
import base64
import uuid
import socket
import time
import mimetypes

from protocol import build_message
from state import user_ip_map

PORT = 50999
DEFAULT_CHUNK_SIZE = 1024

def _ip_from_uid(uid: str):
    if "@" not in uid:
        return None
    ip = uid.split("@",1)[1].strip()
    return ip if __is_valid_ipv4(ip) else None

def __is_valid_ipv4(ip: str) -> bool:
    import re
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip))

def _get_ip_for(uid: str):
    ip = user_ip_map.get(uid)
    if not ip:
        ip = _ip_from_uid(uid)
    return ip

def _send_unicast(fields: dict, to_ip: str, verbose: bool=False):
    msg = build_message(fields).encode("utf-8")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.sendto(msg, (to_ip, PORT))
        if verbose:
            print(f"[FILE] Sent {fields.get('TYPE')} to {to_ip}")
        return True
    except Exception as e:
        if verbose:
            print(f"[FILE] send failed to {to_ip}: {e}")
        return False
    finally:
        s.close()

def send_file(my_uid: str, to_uid: str, filepath: str, chunk_size: int = DEFAULT_CHUNK_SIZE, verbose: bool=False):
    """
    High-level helper: sends FILE_OFFER then streams FILE_CHUNK messages.
    Does not block waiting for FILE_RECEIVED, but prints that transfer is done locally.
    """
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return False

    filesize = os.path.getsize(filepath)
    total_chunks = math.ceil(filesize / chunk_size) if filesize > 0 else 1
    fileid = uuid.uuid4().hex[:8]
    ts = int(time.time())
    token = f"{my_uid}|{ts+3600}|file"  # simple token per RFC

    to_ip = _get_ip_for(to_uid)
    if not to_ip:
        print(f"❌ No IP known for {to_uid}. Wait for their PING/PROFILE.")
        return False

    # Determine MIME type (optional)
    mimetype, _ = mimetypes.guess_type(filepath)
    mimetype = mimetype or "application/octet-stream"

    # 1) Send FILE_OFFER
    offer_fields = {
        "TYPE": "FILE_OFFER",
        "FROM": my_uid,
        "TO": to_uid,
        "FILENAME": os.path.basename(filepath),
        "FILESIZE": str(filesize),
        "FILETYPE": mimetype,
        "FILEID": fileid,
        "TOTAL_CHUNKS": str(total_chunks),
        "CHUNK_SIZE": str(chunk_size),
        "TOKEN": token,
        "MESSAGE_ID": uuid.uuid4().hex[:8],
        "TIMESTAMP": str(ts),
    }
    ok = _send_unicast(offer_fields, to_ip, verbose)
    if not ok:
        print("❌ Failed to send FILE_OFFER.")
        return False

    # 2) Stream chunks
    with open(filepath, "rb") as f:
        idx = 0
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            chunk_b64 = base64.b64encode(chunk).decode("utf-8")
            chunk_fields = {
                "TYPE": "FILE_CHUNK",
                "FROM": my_uid,
                "TO": to_uid,
                "FILEID": fileid,
                "CHUNK_INDEX": str(idx),
                "TOTAL_CHUNKS": str(total_chunks),
                "CHUNK_SIZE": str(len(chunk)),
                "DATA": chunk_b64,
                "TOKEN": token,
                "MESSAGE_ID": uuid.uuid4().hex[:8],
                "TIMESTAMP": str(int(time.time())),
            }
            sent = _send_unicast(chunk_fields, to_ip, verbose)
            if not sent:
                # best-effort retry once
                if verbose: print(f"[FILE] Retry chunk {idx}")
                time.sleep(0.2)
                _send_unicast(chunk_fields, to_ip, verbose)
            idx += 1
            # small throttle to avoid UDP blasting
            time.sleep(0.01)

    print(f"📤 Finished sending '{os.path.basename(filepath)}' -> {to_uid} ({total_chunks} chunks).")
    print("🔔 Wait for FILE_RECEIVED acknowledgement (receiver will send it when assembly completes).")
    return True
