"""Application initialization and setup utilities."""
from ..models.user import User
from ..network.client import get_local_ip
from ..ui.components import get_user_input


def create_user_profile() -> User:
    """Create a user profile through interactive prompts."""
    print("==== Welcome to LSNP ====")
    
    verbose_input = input("Enable Verbose Mode? (y/n): ").lower()
    verbose = verbose_input == "y"
    
    username = get_user_input("Enter your username").strip()
    display_name = get_user_input("Enter your display name").strip()
    status = get_user_input("Enter your status").strip()
    
    # Get real LAN IP
    ip = get_local_ip()
    
    user = User.create(username, display_name, status, ip, verbose)
    
    print(f"\n✅ Profile created! Your User ID: {user.user_id}\n")
    return user
