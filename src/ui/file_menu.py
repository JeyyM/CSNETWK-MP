# src/ui/file_menu.py
import os
import time
from typing import List

from ..core.state import app_state
from ..models.user import Peer
from ..services.file_service import FileService
from ..network.client import NetworkManager

class FileMenu:
    def __init__(self, user, file_service: FileService, network_manager: NetworkManager):
        self.user = user
        self.file_service = file_service
        self.network_manager = network_manager

    def show_file_menu(self) -> None:
        while True:
            active_peers: List[Peer] = self._get_active_peers()
            print("\n=== File Transfer ===")
            print("[S] Send file  [I] Incoming offers  [B] Back")

            choice = input("> ").strip().upper()
            if choice == "B":
                break
            if choice == "S":
                if not active_peers:
                    print("No active peers.")
                    continue
                self._create_send_flow(active_peers)
            elif choice == "I":
                self._list_and_handle_incoming()
            else:
                print("Unknown option.")

    def _get_active_peers(self):
        # exclude self
        return [p for p in app_state.get_active_peers() if p.user_id != self.user.user_id]

    def _display_peers(self, peers):
        for i, peer in enumerate(peers, 1):
            print(f"[{i}] {peer.display_name} ({peer.user_id})")

    def _create_send_flow(self, peers):
        print("\nChoose recipient:")
        self._display_peers(peers)
        sel = input("Invite which #? ").strip()
        try:
            idx = int(sel)-1
            if not (0 <= idx < len(peers)):
                print("Invalid selection.")
                return
            peer = peers[idx]
        except ValueError:
            print("Invalid selection.")
            return

        path = input("File path: ").strip()
        if not os.path.isfile(path):
            print("File does not exist.")
            return
        desc = input("Description (optional): ").strip()
        fid = self.file_service.offer_file(peer.user_id, path, desc)
        if fid:
            print(f"Offer sent (FILEID={fid}). Waiting for accept...")

    def _list_and_handle_incoming(self):
        offers = list(self.file_service.incoming_offers.items())
        if not offers:
            print("No incoming offers.")
            return
        for i, (fid, off) in enumerate(offers, 1):
            print(f"[{i}] {fid} from {off['from']} -> {off['filename']} ({off['filesize']} bytes)")
        sel = input("Select offer # to accept/reject or B: ").strip()
        if sel.upper() == "B":
            return
        try:
            idx = int(sel)-1
            if not (0 <= idx < len(offers)):
                print("Invalid selection.")
                return
            fid = offers[idx][0]
        except ValueError:
            print("Invalid selection.")
            return
        action = input("(A)ccept or (R)eject? ").strip().upper()
        if action == "A":
            ok = self.file_service.accept_offer(fid)
            if ok:
                print("Accepted. Waiting for transfer...")
        elif action == "R":
            ok = self.file_service.reject_offer(fid)
            if ok:
                print("Rejected.")
        else:
            print("Unknown action.")
