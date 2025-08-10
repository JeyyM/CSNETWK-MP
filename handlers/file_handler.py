# handlers/file_handler.py
import os
import base64
import time
import socket
import uuid
from protocol import build_message
from dedupe import seen_before
from state import user_ip_map, profile_data
from protocol import build_message

PORT = 50999
DOWNLOAD_DIR = "downloads"

# token/fileid -> transfer metadata
_file_transfers = {}
# structure:
# _file_transfers[fileid] = {
#   "from": from_uid,
#   "to": to_uid,
#   "filename": filename,
#   "size": filesize,
#   "total_chunks": total_chunks,
#   "chunks": {},            # index -> bytes
#   "received_time": ts
# }

def _ensure_download_dir():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def handle_file_offer(msg: dict, addr, verbose: bool):
    """
    Handle TYPE: FILE_OFFER (RFC 5.8)
    Expected fields: FROM, TO, FILENAME, FILESIZE, FILEID, TOTAL_CHUNKS, CHUNK_SIZE, TOKEN, MESSAGE_ID
    """
    mid = msg.get("MESSAGE_ID")
    if seen_before(mid):
        if verbose: print(f"DROP! Duplicate FILE_OFFER (MESSAGE_ID={mid}) from {addr}")
        return

    from_uid = msg.get("FROM")
    to_uid = msg.get("TO")
    filename = msg.get("FILENAME")
    filesize = msg.get("FILESIZE")
    fileid = msg.get("FILEID") or msg.get("TOKEN")  # accept either FILEID or TOKEN fallback
    total_chunks = msg.get("TOTAL_CHUNKS")
    chunk_size = msg.get("CHUNK_SIZE")

    if not from_uid or not to_uid or not filename or not filesize or not total_chunks or not fileid:
        if verbose: print("[DEBUG] FILE_OFFER missing required fields")
        return

    try:
        filesize = int(filesize)
        total_chunks = int(total_chunks)
    except Exception:
        if verbose: print("[DEBUG] FILE_OFFER invalid numeric fields")
        return

    # record sender IP
    user_ip_map[from_uid] = addr[0]

    # initialize transfer record
    _file_transfers[fileid] = {
        "from": from_uid,
        "to": to_uid,
        "filename": filename,
        "size": filesize,
        "total_chunks": total_chunks,
        "chunks": {},
        "received_time": int(time.time()),
    }

    display = profile_data.get(from_uid, {}).get("display_name", from_uid.split("@")[0])
    print(f"\n📂 FILE OFFER from {display} ({from_uid}): '{filename}' {filesize} bytes — {total_chunks} chunks")
    if verbose:
        print(f"[FILE] Stored transfer record for FILEID={fileid}")

def handle_file_chunk(msg: dict, addr, verbose: bool):
    """
    Handle TYPE: FILE_CHUNK (RFC 5.9)
    Expected fields: FROM, TO, FILEID, CHUNK_INDEX, TOTAL_CHUNKS (optional), CHUNK_SIZE (optional), DATA, MESSAGE_ID
    """
    mid = msg.get("MESSAGE_ID")
    if seen_before(mid):
        if verbose: print(f"DROP! Duplicate FILE_CHUNK (MESSAGE_ID={mid}) from {addr}")
        return

    from_uid = msg.get("FROM")
    to_uid = msg.get("TO")
    fileid = msg.get("FILEID") or msg.get("TOKEN")
    chunk_index_raw = msg.get("CHUNK_INDEX") or msg.get("CHUNK_NO") or msg.get("CHUNK")
    data_b64 = msg.get("DATA")

    if not from_uid or not fileid or chunk_index_raw is None or data_b64 is None:
        if verbose: print("[DEBUG] FILE_CHUNK missing required fields")
        return

    try:
        chunk_index = int(chunk_index_raw)
    except Exception:
        if verbose: print("[DEBUG] FILE_CHUNK invalid CHUNK_INDEX")
        return

    # learn sender ip
    user_ip_map[from_uid] = addr[0]

    if fileid not in _file_transfers:
        if verbose:
            print(f"[DEBUG] FILE_CHUNK received for unknown FILEID={fileid} (ignoring)")
        return

    try:
        chunk_bytes = base64.b64decode(data_b64)
    except Exception:
        if verbose: print("[DEBUG] FILE_CHUNK base64 decode failed")
        return

    transfer = _file_transfers[fileid]
    transfer["chunks"][chunk_index] = chunk_bytes
    if verbose:
        print(f"[FILE] Received chunk {chunk_index+1}/{transfer['total_chunks']} for '{transfer['filename']}'")

    # assemble if complete
    if len(transfer["chunks"]) == transfer["total_chunks"]:
        _assemble_and_ack(fileid, verbose)

def _assemble_and_ack(fileid: str, verbose: bool):
    transfer = _file_transfers.get(fileid)
    if not transfer:
        return

    _ensure_download_dir()
    safe_name = os.path.basename(transfer["filename"])
    out_path = os.path.join(DOWNLOAD_DIR, f"{int(time.time())}_{safe_name}")

    try:
        with open(out_path, "wb") as f:
            for i in range(transfer["total_chunks"]):
                chunk = transfer["chunks"].get(i)
                if chunk is None:
                    raise RuntimeError(f"Missing chunk {i}")
                f.write(chunk)
        print(f"\n✅ File received: {out_path} ({transfer['size']} bytes)")
    except Exception as e:
        print(f"\n❌ Failed to assemble file '{transfer['filename']}': {e}")
        # cleanup but do not send FILE_RECEIVED
        del _file_transfers[fileid]
        return

    # send FILE_RECEIVED back to sender
    from_uid = transfer["to"]  # note: in our stored record 'from' is sender, 'to' is us; but RFC expects FILE_RECEIVED FROM=us TO=sender
    sender_uid = transfer["from"]
    ts = int(time.time())
    mid = uuid.uuid4().hex[:8]
    status = "COMPLETE"

    ack_fields = {
        "TYPE": "FILE_RECEIVED",
        "FROM": from_uid,
        "TO": sender_uid,
        "FILEID": fileid,
        "STATUS": status,
        "TIMESTAMP": ts,
        "MESSAGE_ID": mid,
    }
    msg = build_message(ack_fields).encode("utf-8")

    # attempt unicast to sender IP if known
    sender_ip = user_ip_map.get(sender_uid)
    if sender_ip:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.sendto(msg, (sender_ip, PORT))
            if verbose:
                print(f"[FILE] Sent FILE_RECEIVED to {sender_uid}@{sender_ip}")
        except Exception as e:
            if verbose:
                print(f"[FILE] Failed to send FILE_RECEIVED: {e}")
        finally:
            s.close()
    else:
        if verbose:
            print(f"[FILE] Sender IP unknown, cannot send FILE_RECEIVED for FILEID={fileid}")

    # remove transfer record
    if fileid in _file_transfers:
        del _file_transfers[fileid]
