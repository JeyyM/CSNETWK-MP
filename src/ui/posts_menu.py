"""Posts and feed UI."""
from typing import List

from .components import show_separator, format_time_ago, get_choice
from ..models.user import User, Post
from ..services.message_service import MessageService
from ..core.state import app_state


class PostsMenu:
    """UI for posts and feed management."""
    
    def __init__(self, user: User, message_service: MessageService):
        self.user = user
        self.message_service = message_service
    
    def show_posts_menu(self) -> None:
        """Show posts management interface."""
        while True:
            choice = input(
                "\n[A] Add New Post\n[V] View Posts (Followed)\n[O] View ALL Posts (debug)\n[B] Back to Main Menu\nSelect: "
            ).strip().upper()
            
            if choice == "A":
                self._create_post()
            elif choice == "V":
                self._view_posts(filter_followed=True)
            elif choice == "O":
                self._view_posts(filter_followed=False)
            elif choice == "B":
                break
            else:
                print("❌ Invalid option.\n")
    
    def _create_post(self) -> None:
        """Create a new post."""
        content = input("Enter your post (blank to cancel): ").strip()
        if not content:
            print("❌ Post canceled.\n")
            return
        
        success = self.message_service.create_post(content, self.user)
        if success:
            print("✅ Post broadcasted. Your message is now visible to followers.\n")
        else:
            print("❌ Failed to create post.\n")
    
    def _view_posts(self, filter_followed: bool = True) -> None:
        """View posts feed."""
        posts = self.message_service.get_posts(filter_followed, self.user.user_id)
        
        if not posts:
            print("\n📭 No posts to show with current filter.")
            self._show_debug_info(filter_followed)
            return
        
        self._show_posts_interface(posts)
    
    def _show_debug_info(self, filter_followed: bool) -> None:
        """Show debug information when no posts are found."""
        following = app_state.get_following()
        all_posts = self.message_service.get_posts(False)
        
        print(f"   Following set size: {len(following)}")
        if following:
            print("   Following IDs:")
            for f in sorted(following):
                print(f"     - {f}")
        print(f"   Total posts received: {len(all_posts)}")
        if all_posts:
            print("   Sample authors seen:")
            authors = set(p.user_id for p in all_posts)
            for a in sorted(authors)[:10]:
                print(f"     - {a}")
        print()
    
    def _show_posts_interface(self, posts: List[Post]) -> None:
        """Show posts with like/unlike functionality."""
        while True:
            print("\n==== LSNP Post Feed ====\n")
            post_keys = {}
            
            for idx, post in enumerate(posts, start=1):
                liked = post.has_liked(self.user.user_id)
                like_action = "U" if liked else "L"
                action_text = "unlike" if liked else "like"
                
                print(f"[{idx}] ({format_time_ago(post.age_seconds)}) {post.display_name} ({post.user_id})")
                print(f"📝 {post.content}")
                print(f"❤️ Likes: {post.like_count} – Press [{like_action}{idx}] to {action_text}\n")
                
                post_keys[f"{like_action}{idx}"] = post
            
            print("========================")
            choice = input("\n[L#/U#] Like/Unlike post | [B] Back\n").strip().upper()
            
            if choice == "B":
                break
            
            post = post_keys.get(choice)
            if post:
                is_like = choice.startswith("L")
                self._handle_like_action(post, is_like)
            else:
                print("❌ Invalid post number.")
    
    def _handle_like_action(self, post: Post, is_like: bool) -> None:
        """Handle like/unlike action on a post."""
        success = self.message_service.like_post(post, self.user, is_like)
        if success:
            if is_like:
                print("❤️ You liked the post.\n")
            else:
                print("💔 You unliked the post.\n")
        else:
            action = "like" if is_like else "unlike"
            print(f"❌ Failed to {action} the post.\n")
