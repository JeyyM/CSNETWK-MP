"""Main menu UI."""
from typing import Optional

from .components import show_menu, get_choice
from ..models.user import User


class MainMenu:
    """Main application menu."""
    
    def __init__(self, user: User):
        self.user = user
        self.menu_options = [
            "Toggle Verbose Mode",
            "View Peer Profiles", 
            "Posts Feed",
            "Send a Direct Message",
            "Send a Group Message",
            "Send a File",
            "Play Tic Tac Toe",
            "My Profile",
            "Exit",
            "Make an Expired Token",
            "Make a Mismatched Scope Token"
        ]
    
    def show(self) -> Optional[str]:
        """Show the main menu and get user choice."""
        show_menu("LSNP CLI Menu", self.menu_options)
        
        valid_choices = [str(i) for i in range(len(self.menu_options))]
        choice = get_choice("Select an option", valid_choices)
        
        return choice
    
    def toggle_verbose(self) -> None:
        """Toggle verbose mode."""
        self.user.verbose = not self.user.verbose
        print(f"Verbose Mode {'enabled' if self.user.verbose else 'disabled'}.\n")
    
    def show_profile(self) -> None:
        """Display user profile information."""
        print(f"\nUsername: {self.user.username}")
        print(f"Display Name: {self.user.display_name}")
        print(f"Status: {self.user.status}")
        print(f"User ID: {self.user.user_id}")
        print()
