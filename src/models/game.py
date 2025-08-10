"""Game models for Tic Tac Toe."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum


class Symbol(Enum):
    """Tic Tac Toe symbols."""
    X = "X"
    O = "O"
    EMPTY = ""


class GameState(Enum):
    """Game states."""
    PENDING = "pending"
    ACTIVE = "active"
    FINISHED = "finished"


@dataclass
class TicTacToeInvite:
    """Represents a Tic Tac Toe game invitation."""
    from_user: str
    to_user: str
    game_id: str
    symbol: Symbol
    timestamp: float
    message_id: str
    token: str


@dataclass
class TicTacToeGame:
    """Represents a Tic Tac Toe game."""
    game_id: str
    board: List[Symbol] = field(default_factory=lambda: [Symbol.EMPTY] * 9)
    players: Dict[Symbol, str] = field(default_factory=dict)
    next_symbol: Symbol = Symbol.X
    turn: int = 1
    moves_seen: Set[str] = field(default_factory=set)
    state: GameState = GameState.PENDING
    
    def get_player_symbol(self, user_id: str) -> Optional[Symbol]:
        """Get the symbol for a given player."""
        for symbol, player_id in self.players.items():
            if player_id == user_id:
                return symbol
        return None
    
    def get_opponent(self, user_id: str) -> Optional[str]:
        """Get the opponent's user ID."""
        for player_id in self.players.values():
            if player_id != user_id:
                return player_id
        return None
    
    def is_valid_move(self, position: int) -> bool:
        """Check if a move is valid."""
        return 0 <= position <= 8 and self.board[position] == Symbol.EMPTY
    
    def make_move(self, position: int, symbol: Symbol) -> bool:
        """Make a move on the board."""
        if not self.is_valid_move(position):
            return False
        
        self.board[position] = symbol
        self.next_symbol = Symbol.O if symbol == Symbol.X else Symbol.X
        self.turn += 1
        return True
    
    def check_winner(self) -> Optional[Symbol]:
        """Check if there's a winner."""
        # Winning combinations
        wins = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # columns
            [0, 4, 8], [2, 4, 6]               # diagonals
        ]
        
        for combo in wins:
            symbols = [self.board[i] for i in combo]
            if symbols[0] != Symbol.EMPTY and all(s == symbols[0] for s in symbols):
                return symbols[0]
        return None
    
    def is_draw(self) -> bool:
        """Check if the game is a draw."""
        return all(cell != Symbol.EMPTY for cell in self.board) and self.check_winner() is None
    
    def is_game_over(self) -> bool:
        """Check if the game is over."""
        return self.check_winner() is not None or self.is_draw()
    
    def render_board(self) -> str:
        """Render the board as a string."""
        def cell_char(i: int) -> str:
            return self.board[i].value if self.board[i] != Symbol.EMPTY else " "
        
        return f"""
 {cell_char(0)} | {cell_char(1)} | {cell_char(2)}
-----------
 {cell_char(3)} | {cell_char(4)} | {cell_char(5)}
-----------
 {cell_char(6)} | {cell_char(7)} | {cell_char(8)}
"""
