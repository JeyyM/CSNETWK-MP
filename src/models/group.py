"""Group models for LSNP group functionality."""
from dataclasses import dataclass, field
from typing import Set, Optional
import time


@dataclass
class Group:
    """Represents a user group."""
    group_id: str
    group_name: str
    creator: str
    members: Set[str] = field(default_factory=set)
    created_timestamp: float = field(default_factory=time.time)
    
    def add_member(self, user_id: str) -> None:
        """Add a member to the group."""
        self.members.add(user_id)
    
    def remove_member(self, user_id: str) -> None:
        """Remove a member from the group."""
        self.members.discard(user_id)
    
    def is_member(self, user_id: str) -> bool:
        """Check if user is a member of the group."""
        return user_id in self.members
    
    def is_creator(self, user_id: str) -> bool:
        """Check if user is the creator of the group."""
        return user_id == self.creator
    
    @property
    def member_count(self) -> int:
        """Get the number of members in the group."""
        return len(self.members)


@dataclass
class GroupMessage:
    """Represents a group message."""
    from_user: str
    group_id: str
    content: str
    timestamp: float
    display_name: Optional[str] = None
    
    def format_for_display(self) -> str:
        """Format message for display."""
        sender_name = self.display_name or self.from_user.split("@")[0]
        return f"{sender_name}: {self.content}"
