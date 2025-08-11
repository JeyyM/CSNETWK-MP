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
        mid = msg.get("MESSAGE_ID")
        if mid:
            self.network_manager.send_ack(mid, addr)
        
        from_user = msg.get("FROM")
        to_user   = msg.get("TO")
        game_id   = msg.get("GAMEID")
        symbol    = Symbol.X if msg.get("SYMBOL","X") == "X" else Symbol.O
        other     = Symbol.O if symbol == Symbol.X else Symbol.X  # <-- move outside so it's always defined

        if from_user:
            app_state.update_peer_ip(from_user, addr[0])

        # Ensure local game exists
        game = app_state.get_ttt_game(game_id)
        if not game:
            game = TicTacToeGame(game_id=game_id)
            game.players = {symbol: from_user, other: to_user}
            game.state = GameState.PENDING
            app_state.add_ttt_game(game)

        # NEW: save the invite so UI can show Accept/Reject
        invite = TicTacToeInvite(
            from_user=from_user,
            to_user=to_user,
            game_id=game_id,
            symbol=symbol,
            timestamp=float(msg.get("TIMESTAMP", time.time())),
            message_id=msg.get("MESSAGE_ID",""),
            token=msg.get("TOKEN",""),
        )
        app_state.add_ttt_invite(invite)

        if self.verbose:
            print("\n[GAME] You received a Tic-Tac-Toe invite!")
            print(game.render_board())
            print(f"[GAME] You will play as {other.value}.")

    
    def handle_move(self, msg: dict, addr: tuple) -> None:
        """Handle incoming TICTACTOE_MOVE (apply on receiver, finish if needed)."""
        mid = msg.get("MESSAGE_ID")
        if mid:
            self.network_manager.send_ack(mid, addr)
        
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
        from_user = msg.get("FROM")
        game_id   = msg.get("GAMEID")
        result    = msg.get("RESULT", "DRAW")   # WIN, LOSS, DRAW, FORFEIT
        symbol    = msg.get("SYMBOL")           # winner's symbol if WIN; last mover for DRAW

        if from_user:
            app_state.update_peer_ip(from_user, addr[0])

        game = app_state.get_ttt_game(game_id)

        # Show final board + message even if not verbose, so users actually see it.
        if game:
            print(game.render_board())
        print(f"[GAME] Result for {game_id}: {result}" + (f" (winner {symbol})" if result == "WIN" and symbol else ""))

        # Mark finished & clean up (idempotent)
        if game:
            game.state = GameState.FINISHED
        app_state.remove_ttt_game(game_id)
