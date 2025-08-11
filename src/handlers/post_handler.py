"""Handler for POST messages."""
import time

from ..models.user import Post
from ..core.state import app_state
from ..utils.dedupe import seen_before


class PostHandler:
    """Handles POST messages."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def handle(self, msg: dict, addr: tuple) -> None:
        # Dedupe on MESSAGE_ID (safe even if None)
        mid = msg.get("MESSAGE_ID", "")
        if seen_before(mid):
            return

        # Per spec, POST uses USER_ID (not FROM); no TIMESTAMP field is expected.
        user_id = msg.get("USER_ID", "").strip()
        content = msg.get("CONTENT", "")

        # Ignore posts sent by yourself (to avoid double entry)
        if app_state._local_user_id and user_id == app_state._local_user_id:
            return

        # Basic sanity
        if not user_id or not content:
            if self.verbose:
                print("[POST] DROP malformed POST (missing USER_ID or CONTENT)")
            return

        # TTL present on POST; default 3600
        try:
            ttl = int(msg.get("TTL", "3600"))
        except Exception:
            ttl = 3600

        # Stamp locally (receiver time)
        ts = int(time.time())

        # Optional TTL drop at receive time (usually won't drop immediately)
        if ts + ttl < int(time.time()):
            if self.verbose:
                print(f"[POST] DROP expired POST (mid={mid}) from {user_id}")
            return

        # Resolve display name if we know this peer
        peer = app_state.get_peer(user_id)
        display_name = peer.display_name if peer else (user_id.split("@")[0] or user_id)

        # Persist; follower filtering happens when reading from state (get_posts)
        app_state.add_post(Post(
            user_id=user_id,
            display_name=display_name,
            content=content,
            timestamp=ts,      # local arrival time
            message_id=mid,
            likes=set(),
            ttl=ttl,
        ))

        if self.verbose:
            # Print POST message in detailed format
            print(
                f"TYPE: POST USER_ID: {user_id} \n"
                f"CONTENT: {content} \n"
                f"TTL: {ttl} \n"
                f"MESSAGE_ID: {mid} \n"
                f"TOKEN: {msg.get('TOKEN', '')}"
            )
