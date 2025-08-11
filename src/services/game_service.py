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

ACK_TIMEOUT = 2.0
ACK_ATTEMPTS = 3

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
        
        
        invite_msg = build_message(fields)
        success = self._send_with_ack(opponent_id, fields)
        return game_id if success else None
    
    def send_move(self, game_id: str, position: int, user: User) -> bool:
        """Send a game move. Apply locally first so the sender sees it immediately.
        If the move ends the game, send TICTACTOE_RESULT and clean up.
        """
        game = app_state.get_ttt_game(game_id)
        if not game:
            if getattr(self.network_manager, "verbose", False):
                print(f"[GAME] No local state for game {game_id}")
            return False

        player_symbol = game.get_player_symbol(user.user_id)
        if not player_symbol:
            if getattr(self.network_manager, "verbose", False):
                print(f"[GAME] You are not a participant in {game_id}")
            return False

        opponent_id = game.get_opponent(user.user_id)
        if not opponent_id:
            if getattr(self.network_manager, "verbose", False):
                print(f"[GAME] Opponent not set for {game_id}")
            return False

        # Turn + position checks
        if game.next_symbol != player_symbol:
            if getattr(self.network_manager, "verbose", False):
                print(f"[GAME] Not your turn ({player_symbol.value}) in {game_id}")
            return False
        if not game.is_valid_move(position):
            if getattr(self.network_manager, "verbose", False):
                print(f"[GAME] Invalid position {position} in {game_id}")
            return False

        # Apply locally so sender's board updates immediately
        game.make_move(position, player_symbol)
        game.state = GameState.ACTIVE

        # Check end state locally
        winner = game.check_winner()
        is_draw = game.is_draw()

        if winner or is_draw:
            # Mark finished and announce result to opponent
            game.state = GameState.FINISHED

            # Find winning line if any
            winning_line = None
            if winner:
                wins = [
                    [0,1,2],[3,4,5],[6,7,8],
                    [0,3,6],[1,4,7],[2,5,8],
                    [0,4,8],[2,4,6]
                ]
                for combo in wins:
                    if all(game.board[i] == winner for i in combo):
                        winning_line = ",".join(map(str, combo))
                        break

            message_id = uuid.uuid4().hex[:8]
            timestamp  = int(time.time())
            token      = f"{user.user_id}|{timestamp+3600}|game"

            fields = {
                "TYPE": "TICTACTOE_RESULT",
                "FROM": user.user_id,
                "TO": opponent_id,
                "GAMEID": game_id,
                "MESSAGE_ID": message_id,
                "RESULT": "DRAW" if is_draw else "WIN",   # sender's perspective
                "SYMBOL": player_symbol.value,            # winner's symbol if WIN; last mover's if DRAW
                "TIMESTAMP": timestamp,
                "TOKEN": token,
            }
            if winning_line:
                fields["WINNING_LINE"] = winning_line

            msg = build_message(fields)
            self.network_manager.send_unicast(msg, opponent_id)

            # Optional: print locally
            if getattr(self.network_manager, "verbose", False):
                print(game.render_board())
                print(f"[GAME] {('DRAW' if is_draw else f'{player_symbol.value} WINS')} — game {game_id} finished.")

            # Clean up local state so the game no longer appears active
            app_state.remove_ttt_game(game_id)
            return True

        # Otherwise, send the MOVE packet
        message_id = uuid.uuid4().hex[:8]
        timestamp  = int(time.time())
        token      = f"{user.user_id}|{timestamp+3600}|game"

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
        return self._send_with_ack(opponent_id, fields)

        
    def invite_with_first_move(self, opponent_id: str, position: int, user: User, game_id: str | None = None) -> bool:
        """Inviter (X) sends TICTACTOE_INVITE and immediately the first MOVE, both with ACK retries."""
        # generate game id if not provided (RFC suggests g0..g255)
        if not game_id:
            game_id = f"g{random.randint(0,255)}"

        # Create local game skeleton
        game = TicTacToeGame(game_id=game_id)
        game.players = {
            Symbol.X: user.user_id,
            Symbol.O: opponent_id
        }
        game.state = GameState.PENDING
        app_state.add_ttt_game(game)

        # --- Send INVITE first (with ACK retries) ---
        ts_inv = int(time.time())
        invite_mid = uuid.uuid4().hex[:8]
        invite_fields = {
            "TYPE": "TICTACTOE_INVITE",
            "FROM": user.user_id,
            "TO": opponent_id,
            "GAMEID": game_id,
            "MESSAGE_ID": invite_mid,
            "SYMBOL": "X",                     # inviter plays X
            "TIMESTAMP": ts_inv,
            "TOKEN": f"{user.user_id}|{ts_inv+3600}|game",
        }
        if not self._send_with_ack(opponent_id, invite_fields):
            return False

        # --- Apply the first move locally ---
        if game.next_symbol != Symbol.X:
            game.next_symbol = Symbol.X
        if not game.is_valid_move(position):
            if getattr(self.network_manager, "verbose", False):
                print(f"[GAME] Invalid first position {position} for {game_id}")
            return False

        game.make_move(position, Symbol.X)
        game.state = GameState.ACTIVE

        # --- Send MOVE (with ACK retries) ---
        ts_mv = int(time.time())
        move_mid = uuid.uuid4().hex[:8]
        move_fields = {
            "TYPE": "TICTACTOE_MOVE",
            "FROM": user.user_id,
            "TO": opponent_id,
            "GAMEID": game_id,
            "POSITION": position,
            "SYMBOL": "X",
            "MESSAGE_ID": move_mid,
            "TIMESTAMP": ts_mv,
            "TOKEN": f"{user.user_id}|{ts_mv+3600}|game",
        }
        return self._send_with_ack(opponent_id, move_fields)
        
    def accept_invite(self, invite: TicTacToeInvite, position: int, user: User) -> bool:
        my_symbol = Symbol.O if invite.symbol == Symbol.X else Symbol.X

        game = app_state.get_ttt_game(invite.game_id)
        if not game:
            game = TicTacToeGame(game_id=invite.game_id)
            other = Symbol.O if invite.symbol == Symbol.X else Symbol.X
            game.players = {invite.symbol: invite.from_user, other: user.user_id}
            game.state = GameState.PENDING
            app_state.add_ttt_game(game)

        # guard turn just for UX; if MOVE from X hasn’t landed yet, this will say “not your turn”
        if game.next_symbol != my_symbol:
            if getattr(self.network_manager, "verbose", False):
                print(f"[GAME] Not your turn yet in {invite.game_id} "
                    f"(expected {game.next_symbol.value}, you are {my_symbol.value}).")
            return False

        ok = self.send_move(invite.game_id, position, user)
        if ok:
            app_state.remove_ttt_invite(invite.from_user, invite.game_id)
        return ok


    
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

    def _send_with_ack(self, to_user_id: str, fields: dict) -> bool:
        """Send a message and wait for ACK with retries."""
        msg = build_message(fields)
        mid = fields.get("MESSAGE_ID")
        evt = app_state.mark_ack_pending(mid)

        for attempt in range(1, ACK_ATTEMPTS + 1):
            try:
                self.network_manager.send_unicast(msg, to_user_id)
                if getattr(self.network_manager, "verbose", False):
                    print(f"[ACK] Sent {fields['TYPE']} attempt {attempt}/{ACK_ATTEMPTS} mid={mid}")
                
                # Wait for ACK
                if evt.wait(ACK_TIMEOUT):
                    if getattr(self.network_manager, "verbose", False):
                        print(f"[ACK] Received ACK for {mid}")
                    app_state.drop_ack_wait(mid)  # Clean up
                    return True
                
                if getattr(self.network_manager, "verbose", False):
                    print(f"[ACK] Timeout waiting for {mid}, retrying...")
                
            except Exception as e:
                if getattr(self.network_manager, "verbose", False):
                    print(f"[ACK] Send error on attempt {attempt}: {e}")
                if attempt < ACK_ATTEMPTS:
                    time.sleep(0.5)  # Short delay before retry

        # Give up after all attempts
        if getattr(self.network_manager, "verbose", False):
            print(f"[ACK] Giving up on {mid} after {ACK_ATTEMPTS} attempts")
        app_state.drop_ack_wait(mid)
        return False