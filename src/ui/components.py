"""Base UI components and utilities."""
import os
from typing import List, Optional


def clear_console() -> None:
    """Clear the console screen."""
    os.system("cls" if os.name == "nt" else "clear")


def get_user_input(prompt: str, default: str = "") -> str:
    """Get user input with optional default value."""
    if default:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    return input(f"{prompt}: ").strip()


def show_menu(title: str, options: List[str]) -> None:
    """Display a menu with title and options."""
    print(f"==== {title} ====\n")
    for i, option in enumerate(options):
        print(f"[{i}] {option}")
    print()


def format_time_ago(seconds: int) -> str:
    """Format seconds into human readable time ago."""
    if seconds < 60:
        return f"{seconds}s ago"
    elif seconds < 3600:
        return f"{seconds // 60}m ago"
    else:
        return f"{seconds // 3600}h ago"


def format_list_with_numbers(items: List[str], start_num: int = 1) -> str:
    """Format a list with numbers."""
    return "\n".join(f"[{i}] {item}" for i, item in enumerate(items, start_num))


def get_choice(prompt: str, valid_choices: List[str]) -> Optional[str]:
    """Get user choice from valid options."""
    while True:
        choice = input(f"{prompt}: ").strip().upper()
        if choice in valid_choices:
            return choice
        print(f"❌ Invalid choice. Valid options: {', '.join(valid_choices)}")


def paginate_list(items: List[str], page_size: int = 10) -> List[List[str]]:
    """Paginate a list into chunks."""
    return [items[i:i + page_size] for i in range(0, len(items), page_size)]


def show_separator(char: str = "─", length: int = 40) -> None:
    """Show a separator line."""
    print(char * length)
