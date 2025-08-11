# dedupe.py
from collections import deque

_SEEN_IDS: set[str] = set()
_SEEN_ORDER: deque[str] = deque(maxlen=4096)

def seen_before(message_id: str | None) -> bool:
    """Return True if we've processed this MESSAGE_ID before; otherwise record it."""
    if not message_id:
        return False
    if message_id in _SEEN_IDS:
        return True
    _SEEN_IDS.add(message_id)
    _SEEN_ORDER.append(message_id)
    while len(_SEEN_IDS) > _SEEN_ORDER.maxlen:
        old = _SEEN_ORDER.popleft()
        _SEEN_IDS.discard(old)
    return False
