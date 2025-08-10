"""User model and related data structures."""
from dataclasses import dataclass
from typing import Optional
import time


@dataclass
class User:
    """Represents a user in the LSNP network."""
    username: str
    display_name: str
    status: str
    user_id: str
    ip: str
    verbose: bool = False
    
    @classmethod
    def create(cls, username: str, display_name: str, status: str, ip: str, verbose: bool = False) -> 'User':
        """Create a new User instance with generated user_id."""
        user_id = f"{username}@{ip}"
        return cls(username, display_name, status, user_id, ip, verbose)


@dataclass
class Peer:
    """Represents a peer in the network."""
    user_id: str
    display_name: str
    status: str
    ip: str
    last_seen: float
    
    @property
    def is_active(self) -> bool:
        """Check if peer has been seen recently (within 60 seconds)."""
        return time.time() - self.last_seen < 60
    
    @property
    def seconds_since_seen(self) -> int:
        """Get seconds since peer was last seen."""
        return int(time.time() - self.last_seen)


@dataclass
class DirectMessage:
    """Represents a direct message."""
    from_user: str
    to_user: str
    content: str
    timestamp: float
    message_id: Optional[str] = None
    display_name: Optional[str] = None
    
    def format_for_display(self, sender_name: str) -> str:
        """Format message for display in chat."""
        return f"{sender_name}: {self.content}"


@dataclass
class Post:
    """Represents a social media post."""
    user_id: str
    display_name: str
    content: str
    timestamp: float
    message_id: str
    likes: set
    ttl: int = 3600
    
    @property
    def age_seconds(self) -> int:
        """Get age of post in seconds."""
        return int(time.time() - self.timestamp)
    
    @property
    def like_count(self) -> int:
        """Get number of likes."""
        return len(self.likes)
    
    def add_like(self, user_id: str) -> None:
        """Add a like from a user."""
        self.likes.add(user_id)
    
    def remove_like(self, user_id: str) -> None:
        """Remove a like from a user."""
        self.likes.discard(user_id)
    
    def has_liked(self, user_id: str) -> bool:
        """Check if user has liked this post."""
        return user_id in self.likes
