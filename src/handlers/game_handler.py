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
        from_user = msg.get("FROM")
        to_user   = msg.get("TO")
        game_id   = msg.get("GAMEID")
        symbol    = Symbol.X if msg.get("SYMBOL","X") == "X" else Symbol.O

        if from_user:
            app_state.update_peer_ip(from_user, addr[0])

        game = app_state.get_ttt_game(game_id)
        if not game:
            game = TicTacToeGame(game_id=game_id)
            # inviter uses `symbol`, receiver uses the other one
            other = Symbol.O if symbol == Symbol.X else Symbol.X
            game.players = {symbol: from_user, other: to_user}
            game.state = GameState.PENDING
            app_state.add_ttt_game(game)

        if self.verbose:
            print("\n[GAME] You received a Tic-Tac-Toe invite!")
            print(game.render_board())  # shows 0–8 indices on empties
            print(f"[GAME] You will play as {other.value}.")
            # your UI can then prompt: "Enter your first move [0-8] to ACCEPT, or 'n' to reject:"
    
    def handle_move(self, msg: dict, addr: tuple) -> None:
        """Handle incoming TICTACTOE_MOVE (apply on receiver, finish if needed)."""
        from_user = msg.get("FROM")
        game_id   = msg.get("GAMEID")
        try:
            position = int(msg.get("POSITION", -1))
        except ValueError:
            position = -1
        symbol_str = msg.get("SYMBOL", "")

        # Map symbol string to enum
        if symbol_str not in ("X", "O"):
            if self.verbose:
                print("[GAME] Invalid symbol in move")
            return
        symbol = Symbol.X if symbol_str == "X" else Symbol.O

        # Track sender IP
        if from_user:
            app_state.update_peer_ip(from_user, addr[0])

        game = app_state.get_ttt_game(game_id)
        if not game:
            if self.verbose:
                print(f"[GAME] MOVE for unknown game {game_id}")
            return

        # Enforce turn and symbol ownership
        if game.next_symbol != symbol:
            if self.verbose:
                print(f"[GAME] Out-of-turn move by {from_user} in {game_id}")
            return

        # Optional dedupe (by turn/pos/symbol)
        key = f"{game.turn}:{position}:{symbol.value}"
        if key in game.moves_seen:
            return
        game.moves_seen.add(key)

        # Validate move
        if not game.is_valid_move(position):
            if self.verbose:
                print(f"[GAME] Invalid move {position} in {game_id}")
            return

        # Apply
        game.make_move(position, symbol)
        game.state = GameState.ACTIVE

        # Print board (RFC suggests printing board on MOVE)
        if self.verbose:
            print(game.render_board())
            print(f"[GAME] Next: {game.next_symbol.value}")

        # Finish if win/draw (do NOT send RESULT here—only mover sends)
        if game.check_winner() or game.is_draw():
            game.state = GameState.FINISHED
            if self.verbose:
                if game.is_draw():
                    print(f"[GAME] DRAW in {game_id}")
                else:
                    print(f"[GAME] {symbol.value} wins in {game_id}")
            # Remove locally so it disappears from active
            app_state.remove_ttt_game(game_id)
    
    def handle_result(self, msg: dict, addr: tuple) -> None:
        """Handle incoming TICTACTOE_RESULT (finalize + cleanup)."""
        from_user = msg.get("FROM")
        game_id   = msg.get("GAMEID")
        result    = msg.get("RESULT", "DRAW")     # WIN, LOSS, DRAW, FORFEIT (sender's perspective)
        symbol    = msg.get("SYMBOL")             # winner's symbol if WIN; last mover for DRAW
        # winning_line = msg.get("WINNING_LINE")  # optional

        if from_user:
            app_state.update_peer_ip(from_user, addr[0])

        game = app_state.get_ttt_game(game_id)
        if game:
            # Show final board if you still have it
            if self.verbose:
                print(game.render_board())
                print(f"[GAME] Result received for {game_id}: {result} (symbol={symbol})")

            # Mark finished and clean up
            game.state = GameState.FINISHED

        # Remove game state regardless (idempotent)
        app_state.remove_ttt_game(game_id)
