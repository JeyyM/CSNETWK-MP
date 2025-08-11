"""Tic Tac Toe game UI."""
from typing import List, Optional

from .components import get_choice
from ..models.user import User, Peer
from ..models.game import TicTacToeGame, TicTacToeInvite, Symbol, GameState
from ..services.game_service import GameService
from ..services.user_service import UserService
from ..core.state import app_state


class GameMenu:
    """UI for Tic Tac Toe game management."""
    
    def __init__(self, user: User, game_service: GameService, user_service: UserService):
        self.user = user
        self.game_service = game_service
        self.user_service = user_service
    
    def show_game_menu(self) -> None:
        """Show Tic Tac Toe game interface."""
        while True:
            active_peers = self.user_service.get_active_peers(self.user.user_id)
            
            print("\n=== Tic Tac Toe ===")
            print("[N] New game  [B] Back")
            
            if not active_peers:
                print("No active peers.")
                choice = get_choice("Pick option", ["N", "B"])
                if choice == "B":
                    break
                elif choice == "N":
                    print("No peers to invite.")
                    continue
            else:
                self._display_peers_with_game_status(active_peers)
                
                valid_choices = ["N", "B"] + [str(i) for i in range(1, len(active_peers) + 1)]
                choice = get_choice("Pick user #, or N/B", valid_choices)
                
                if choice == "B":
                    break
                elif choice == "N":
                    self._create_new_game(active_peers)
                else:
                    try:
                        peer_index = int(choice) - 1
                        if 0 <= peer_index < len(active_peers):
                            self._handle_peer_interaction(active_peers[peer_index])
                    except ValueError:
                        print("Invalid selection.")
    
    def _display_peers_with_game_status(self, peers: List[Peer]) -> None:
        """Display peers with their game status."""
        for i, peer in enumerate(peers, 1):
            status = self.game_service.get_user_game_status(peer.user_id)
            status_text = f" ({status})" if status and status != "Idle" else ""
            print(f"[{i}] {peer.display_name} ({peer.user_id}){status_text}")
    
    def _create_new_game(self, peers: List[Peer]) -> None:
        """Create a new game invitation."""
        print("\nChoose opponent:")
        for i, peer in enumerate(peers, 1):
            print(f"[{i}] {peer.display_name} ({peer.user_id})")
        
        choice = input("Invite which #? ").strip()
        try:
            peer_index = int(choice) - 1
            if 0 <= peer_index < len(peers):
                opponent = peers[peer_index]
                self._send_game_invite(opponent)
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid selection.")
    
    def _send_game_invite(self, opponent: Peer) -> None:
        """Send a game invite to an opponent."""
        symbol_choice = input("Play as X or O? [X/O]: ").strip().upper()
        if symbol_choice not in {"X", "O"}:
            print("Symbol must be X or O.")
            return
        
        symbol = Symbol(symbol_choice)

        if symbol == Symbol.X:
            # Show a numbered board for context, then ask for first move
            preview = TicTacToeGame(game_id="preview")
            print(preview.render_board())
            first = input("Your first move [0-8]: ").strip()
            try:
                pos = int(first)
                if not (0 <= pos <= 8):
                    raise ValueError
            except ValueError:
                print("Invalid position. Must be 0-8.")
                return

            ok = self.game_service.invite_with_first_move(opponent.user_id, pos, self.user)
            if ok:
                print("Invite sent with your first move.")
            else:
                print("Invite failed to send.")
        else:
            game_id = self.game_service.create_game_invite(opponent.user_id, symbol, self.user)
            if game_id:
                print(f"Invite sent for game {game_id}.")
            else:
                print("Invite failed to send.")
    
    def _handle_peer_interaction(self, peer: Peer) -> None:
        """Handle interaction with a specific peer (invites/games)."""
        # Check for invites from this peer
        invites = self.game_service.get_invites_for_user(peer.user_id)
        if invites:
            self._handle_game_invite(invites[0])
            return
        
        # Check for ongoing games with this peer
        games = [g for g in self.game_service.get_games_for_user(self.user.user_id) 
                if peer.user_id in g.players.values()]
        
        if not games:
            print("No invite or ongoing game with this user.")
            return
        
        # Handle ongoing game
        if len(games) > 1:
            print("Multiple games found:")
            for i, game in enumerate(games, 1):
                print(f"  [{i}] {game.game_id}")
            try:
                choice = int(input("Pick game #: ").strip())
                game = games[choice - 1]
            except (ValueError, IndexError):
                print("Invalid selection.")
                return
        else:
            game = games[0]
        
        self._play_game(game)
    
    def _handle_game_invite(self, invite: TicTacToeInvite) -> None:
        """Handle an incoming game invite."""
        inviter_peer = self.user_service.get_peer(invite.from_user)
        inviter_name = inviter_peer.display_name if inviter_peer else invite.from_user

        my_symbol = Symbol.O if invite.symbol == Symbol.X else Symbol.X
        print(f"\nInvite detected from {inviter_name} (game {invite.game_id}). You are '{my_symbol.value}'.")

        # Show a numbered board for context
        game = self.game_service.get_game(invite.game_id)
        if game:
            print(game.render_board())
        else:
            print(TicTacToeGame(game_id="preview").render_board())

        while True:
            choice = input("[A]ccept with move, [R]eject, [B]ack: ").strip().lower()
            if choice == "b":
                return
            if choice == "r":
                success = self.game_service.reject_invite(invite, self.user)
                print("Invite rejected." if success else "Failed to reject invite.")
                return
            if choice == "a":
                move = input("Enter your first move [0-8]: ").strip()
                try:
                    position = int(move)
                    if not (0 <= position <= 8):
                        raise ValueError
                except ValueError:
                    print("Invalid position. Must be 0-8.")
                    continue
                success = self.game_service.accept_invite(invite, position, self.user)
                if success:
                    print(f"Accepted invite. Played {position}.")
                    updated = self.game_service.get_game(invite.game_id)
                    if updated:
                        print(updated.render_board())
                else:
                    print("Failed to send your move.")
                return
            print("Please choose A, R, or B.")

    def _play_game(self, game: TicTacToeGame) -> None:
        """Play an active game."""
        print(game.render_board())
        
        # Get player's symbol
        player_symbol = game.get_player_symbol(self.user.user_id)
        if not player_symbol:
            print("You are not a player in this game.")
            return
        
        if game.next_symbol != player_symbol:
            print(f"Waiting for opponent ({game.next_symbol.value}'s turn).")
            return
        
        if game.state != GameState.ACTIVE:
            print("Game is not active.")
            return
        
        move = input(f"Your move as {player_symbol.value} [0-8] (or 'b' to back): ").strip().lower()
        
        if move == "b":
            return
        
        try:
            position = int(move)
            if not (0 <= position <= 8):
                raise ValueError("Position must be 0-8")
            
            if not game.is_valid_move(position):
                print("Invalid move - position already taken.")
                return
            
            success = self.game_service.send_move(game.game_id, position, self.user)
            if success:
                # Do NOT apply the move here; send_move already applied it locally.
                updated = self.game_service.get_game(game.game_id) or game
                print(updated.render_board())

                # Check for end state on the updated object
                winner = updated.check_winner()
                if winner:
                    winner_id = updated.players.get(winner)
                    if winner_id == self.user.user_id:
                        print("🎉 You won!")
                    else:
                        peer = self.user_service.get_peer(winner_id)
                        winner_name = peer.display_name if peer else winner_id
                        print(f"😞 {winner_name} won!")
                elif updated.is_draw():
                    print("🤝 It's a draw!")
            else:
                print("Move send failed.")
        except ValueError:
            print("Invalid input.")
