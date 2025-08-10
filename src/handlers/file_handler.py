# src/handlers/file_handler.py
from typing import Tuple
from ..core import state as core_state

def handle_file_message(msg: dict, addr: Tuple[str,int]) -> None:
    app = core_state.app_state
    file_service = getattr(app, "file_service", None)
    if not file_service:
        if getattr(app, "verbose", False):
            print("[FILE] No file service configured.")
        return

    mtype = msg.get("TYPE", "")
    if mtype == "FILE_OFFER":
        file_service.handle_file_offer_incoming(msg, addr)
    elif mtype == "FILE_ACCEPT":
        file_service.handle_file_accept(msg, addr)
    elif mtype == "FILE_REJECT":
        fid = msg.get("FILEID")
        if fid and fid in file_service.outgoing:
            print(f"⚠️ Remote rejected file offer {fid}")
            file_service.outgoing.pop(fid, None)
    elif mtype == "FILE_CHUNK":
        file_service.handle_file_chunk_incoming(msg, addr)
    elif mtype == "FILE_RECEIVED":
        file_service.handle_file_received(msg, addr)
