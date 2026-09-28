import uuid

import uuid6


def new_id() -> uuid.UUID:
    """Return a time-ordered UUID v7 (PRD §7: all primary keys are UUID v7)."""
    return uuid.UUID(bytes=uuid6.uuid7().bytes)
