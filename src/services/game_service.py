"""Game service for Tic Tac Toe."""
import time
import uuid
import random
from typing import List, Optional

from ..models.user import User
from ..models.game import TicTacToeGame, TicTacToeInvite, Symbol, GameState
from ..network.client import NetworkManager
from ..network.protocol import build_message
from ..core.state import app_state


class GameService:
    """Service for game-related operations."""
    
    def __init__(self, network_manager: NetworkManager):
        self.network_manager = network_manager
    
    def create_game_invite(self, opponent_id: str, symbol: Symbol, user: User) -> Optional[str]:
        """Create and send a game invite."""
        game_id = f"g{random.randint(0, 255)}"
        message_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        token = f"{user.user_id}|{timestamp+3600}|game"

        # Create local game state
        other_symbol = Symbol.O if symbol == Symbol.X else Symbol.X
        game = TicTacToeGame(
            game_id=game_id,
            players={symbol: user.user_id, other_symbol: opponent_id},
            state=GameState.PENDING
        )
        app_state.add_ttt_game(game)

        # Send invite
        fields = {
            "TYPE": "TICTACTOE_INVITE",
            "FROM": user.user_id,
            "TO": opponent_id,
            "GAMEID": game_id,
            "SYMBOL": symbol.value,
            "MESSAGE_ID": message_id,
            "TIMESTAMP": timestamp,
            "TOKEN": token,
        }
        invite_msg = build_message(fields)
        
        success = self.network_manager.send_unicast(invite_msg, opponent_id)
        return game_id if success else None
    
    def send_move(self, game_id: str, position: int, user: User) -> bool:
        """Send a game move."""
        game = app_state.get_ttt_game(game_id)
        if not game:
            return False
        
        player_symbol = game.get_player_symbol(user.user_id)
        if not player_symbol:
            return False
        
        opponent_id = game.get_opponent(user.user_id)
        if not opponent_id:
            return False

        message_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        token = f"{user.user_id}|{timestamp+3600}|game"

        fields = {
            "TYPE": "TICTACTOE_MOVE",
            "FROM": user.user_id,
            "TO": opponent_id,
            "GAMEID": game_id,
            "POSITION": position,
            "SYMBOL": player_symbol.value,
            "MESSAGE_ID": message_id,
            "TIMESTAMP": timestamp,
            "TOKEN": token,
        }
        move_msg = build_message(fields)
        
        return self.network_manager.send_unicast(move_msg, opponent_id)
    
    def accept_invite(self, invite: TicTacToeInvite, first_move: int, user: User) -> bool:
        """Accept a game invite with first move."""
        # Remove the invite
        app_state.remove_ttt_invite(invite.from_user, invite.game_id)
        
        # Make sure game exists locally
        game = app_state.get_ttt_game(invite.game_id)
        if not game:
            # Create game state
            my_symbol = Symbol.O if invite.symbol == Symbol.X else Symbol.X
            game = TicTacToeGame(
                game_id=invite.game_id,
                players={invite.symbol: invite.from_user, my_symbol: user.user_id},
                state=GameState.ACTIVE
            )
            app_state.add_ttt_game(game)
        
        # Send move
        return self.send_move(invite.game_id, first_move, user)
    
    def reject_invite(self, invite: TicTacToeInvite, user: User) -> bool:
        """Reject a game invite."""
        timestamp = int(time.time())
        message_id = uuid.uuid4().hex[:8]
        my_symbol = Symbol.O if invite.symbol == Symbol.X else Symbol.X
        
        result_fields = {
            "TYPE": "TICTACTOE_RESULT",
            "FROM": user.user_id,
            "TO": invite.from_user,
            "GAMEID": invite.game_id,
            "MESSAGE_ID": message_id,
            "RESULT": "FORFEIT",
            "SYMBOL": my_symbol.value,
            "TIMESTAMP": timestamp,
            "TOKEN": f"{user.user_id}|{timestamp+3600}|game",
        }
        result_msg = build_message(result_fields)
        
        success = self.network_manager.send_unicast(result_msg, invite.from_user)
        
        if success:
            # Clean up local state
            app_state.remove_ttt_invite(invite.from_user, invite.game_id)
            app_state.remove_ttt_game(invite.game_id)
        
        return success
    
    def get_game(self, game_id: str) -> Optional[TicTacToeGame]:
        """Get a game by ID."""
        return app_state.get_ttt_game(game_id)
    
    def get_games_for_user(self, user_id: str) -> List[TicTacToeGame]:
        """Get all games for a user."""
        return app_state.get_ttt_games_for_user(user_id)
    
    def get_invites_for_user(self, user_id: str) -> List[TicTacToeInvite]:
        """Get all invites from a user."""
        return app_state.get_ttt_invites_for_user(user_id)
    
    def get_user_game_status(self, peer_id: str) -> str:
        """Get game status for a user (for UI display)."""
        invites = self.get_invites_for_user(peer_id)
        games = self.get_games_for_user(peer_id)
        
        status_parts = []
        if invites:
            status_parts.append("Has Invite")
        if any(g.state == GameState.ACTIVE for g in games):
            status_parts.append("Ongoing")
        
        return ", ".join(status_parts) if status_parts else "Idle"
