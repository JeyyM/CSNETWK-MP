"""Handler for game messages."""
import time

from ..models.game import TicTacToeInvite, TicTacToeGame, Symbol, GameState
from ..network.client import NetworkManager
from ..network.protocol import build_message
from ..core.state import app_state


class GameHandler:
    """Handles game-related messages."""
    
    def __init__(self, network_manager: NetworkManager, verbose: bool = False):
        self.network_manager = network_manager
        self.verbose = verbose
    
    def handle_invite(self, msg: dict, addr: tuple) -> None:
        """Handle a TICTACTOE_INVITE message."""
        from_user = msg.get("FROM")
        to_user = msg.get("TO")
        game_id = msg.get("GAMEID")
        symbol_str = msg.get("SYMBOL")
        message_id = msg.get("MESSAGE_ID")
        timestamp = float(msg.get("TIMESTAMP", time.time()))
        token = msg.get("TOKEN", "")
        
        if not all([from_user, game_id, symbol_str]):
            if self.verbose:
                print("TICTACTOE_INVITE missing required fields")
            return
        
        try:
            symbol = Symbol(symbol_str)
        except ValueError:
            if self.verbose:
                print(f"TICTACTOE_INVITE invalid symbol: {symbol_str}")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(from_user, addr[0])
        
        # Create invite
        invite = TicTacToeInvite(
            from_user=from_user,
            to_user=to_user or "",
            game_id=game_id,
            symbol=symbol,
            timestamp=timestamp,
            message_id=message_id or "",
            token=token
        )
        
        app_state.add_ttt_invite(invite)
        
        # Create game shell if it doesn't exist
        if not app_state.get_ttt_game(game_id):
            other_symbol = Symbol.O if symbol == Symbol.X else Symbol.X
            game = TicTacToeGame(
                game_id=game_id,
                players={symbol: from_user, other_symbol: to_user or ""},
                state=GameState.PENDING
            )
            app_state.add_ttt_game(game)
        
        # Get display name for notification
        peer = app_state.get_peer(from_user)
        display_name = peer.display_name if peer else from_user
        
        print(f"\n🎮 Tic Tac Toe invite from {display_name}! (Game: {game_id})")
        print("> ", end="", flush=True)
        
        if self.verbose:
            print(f"TICTACTOE_INVITE from {from_user} for game {game_id}")
    
    def handle_move(self, msg: dict, addr: tuple) -> None:
        """Handle a TICTACTOE_MOVE message."""
        from_user = msg.get("FROM")
        game_id = msg.get("GAMEID")
        position_str = msg.get("POSITION")
        symbol_str = msg.get("SYMBOL")
        
        if not all([from_user, game_id, position_str, symbol_str]):
            if self.verbose:
                print("TICTACTOE_MOVE missing required fields")
            return
        
        try:
            position = int(position_str)
            symbol = Symbol(symbol_str)
        except (ValueError, TypeError):
            if self.verbose:
                print("TICTACTOE_MOVE invalid position or symbol")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(from_user, addr[0])
        
        # Get game
        game = app_state.get_ttt_game(game_id)
        if not game:
            if self.verbose:
                print(f"TICTACTOE_MOVE: Game {game_id} not found")
            return
        
        # Validate and make move
        if not game.is_valid_move(position):
            if self.verbose:
                print(f"TICTACTOE_MOVE: Invalid move {position} for game {game_id}")
            return
        
        game.make_move(position, symbol)
        game.state = GameState.ACTIVE
        
        # Check for game end
        winner = game.check_winner()
        is_draw = game.is_draw()
        
        if winner or is_draw:
            game.state = GameState.FINISHED
            if winner:
                winner_id = game.players.get(winner)
                peer = app_state.get_peer(winner_id) if winner_id else None
                winner_name = peer.display_name if peer else (winner_id or "Unknown")
                print(f"\n🎉 Game {game_id} won by {winner_name} ({winner.value})!")
            else:
                print(f"\n🤝 Game {game_id} ended in a draw!")
        
        # Display board
        print(f"\n🎮 Game {game_id} - Move by {from_user}:")
        print(game.render_board())
        
        if game.state == GameState.ACTIVE:
            print(f"Next turn: {game.next_symbol.value}")
        
        print("> ", end="", flush=True)
        
        if self.verbose:
            print(f"TICTACTOE_MOVE: {from_user} played {symbol.value} at {position}")
    
    def handle_result(self, msg: dict, addr: tuple) -> None:
        """Handle a TICTACTOE_RESULT message."""
        from_user = msg.get("FROM")
        game_id = msg.get("GAMEID")
        result = msg.get("RESULT")
        
        if not all([from_user, game_id, result]):
            if self.verbose:
                print("TICTACTOE_RESULT missing required fields")
            return
        
        # Update sender's IP
        app_state.update_peer_ip(from_user, addr[0])
        
        if result == "FORFEIT":
            # Clean up game state
            app_state.remove_ttt_game(game_id)
            app_state.remove_ttt_invite(from_user, game_id)
            
            peer = app_state.get_peer(from_user)
            display_name = peer.display_name if peer else from_user
            
            print(f"\n🚫 {display_name} forfeited game {game_id}")
            print("> ", end="", flush=True)
        
        if self.verbose:
            print(f"TICTACTOE_RESULT: {from_user} sent {result} for game {game_id}")
