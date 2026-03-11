"""Subscription runtime for in-memory subscription management.

Loads subscriptions from SQLite on startup, maintains in-memory indices
for efficient lookup by cell_id and event_type.
"""

import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from src.core.database import engine
from src.models import Subscription, SubscriptionEntry

logger = logging.getLogger(__name__)


class SubscriptionRuntime:
    """Manages subscriptions in memory with DB persistence."""

    __slots__ = ("_subscriptions", "_by_cell", "_by_cell_event")

    def __init__(self):
        # Main storage: subscription_id -> SubscriptionEntry
        self._subscriptions: dict[str, SubscriptionEntry] = {}
        # Index: cell_id -> set of subscription_ids
        self._by_cell: dict[int, set[str]] = {}
        # Index: (cell_id, event_type) -> set of subscription_ids
        self._by_cell_event: dict[tuple[int, str], set[str]] = {}

    def load_from_db(self) -> None:
        """Load all subscriptions from database into memory."""
        now = datetime.now()

        with Session(engine) as session:
            subs = session.exec(select(Subscription)).all()

            loaded = 0
            expired = 0
            for sub in subs:
                # Skip and delete expired subscriptions
                if sub.expiry_time < now:
                    session.delete(sub)
                    expired += 1
                    continue

                entry = SubscriptionEntry(
                    id=sub.id,
                    callback_url=sub.callback_url,
                    cell_ids=sub.cell_ids,
                    event_types=sub.event_types,
                    created_at=sub.created_at,
                )
                self._add_to_indices(entry)
                loaded += 1

            if expired > 0:
                session.commit()
                logger.info("Cleaned up %d expired subscriptions", expired)

        logger.info("Loaded %d subscriptions from database", loaded)

    def _add_to_indices(self, entry: SubscriptionEntry) -> None:
        """Add subscription to all indices."""
        if entry.id is None:
            return

        self._subscriptions[entry.id] = entry

        for cell_id in entry.cell_ids:
            self._by_cell.setdefault(cell_id, set()).add(entry.id)
            for event_type in entry.event_types:
                key = (cell_id, event_type)
                self._by_cell_event.setdefault(key, set()).add(entry.id)

    def _remove_from_indices(self, entry: SubscriptionEntry) -> None:
        """Remove subscription from all indices."""
        if entry.id is None:
            return

        self._subscriptions.pop(entry.id, None)

        for cell_id in entry.cell_ids:
            if cell_id in self._by_cell:
                self._by_cell[cell_id].discard(entry.id)
                if not self._by_cell[cell_id]:
                    del self._by_cell[cell_id]

            for event_type in entry.event_types:
                key = (cell_id, event_type)
                if key in self._by_cell_event:
                    self._by_cell_event[key].discard(entry.id)
                    if not self._by_cell_event[key]:
                        del self._by_cell_event[key]

    def add(self, entry: SubscriptionEntry) -> SubscriptionEntry:
        """Add subscription to memory and persist to DB."""
        with Session(engine) as session:
            db_sub = Subscription(
                callback_url=entry.callback_url,
                cell_ids=entry.cell_ids,
                event_types=entry.event_types,
            )
            session.add(db_sub)
            session.commit()
            session.refresh(db_sub)

            entry.id = db_sub.id
            entry.created_at = db_sub.created_at

        self._add_to_indices(entry)
        logger.info("Added subscription %s for cells %s", entry.id, entry.cell_ids)
        return entry

    def remove(self, subscription_id: str) -> bool:
        """Remove subscription from memory and DB."""
        entry = self._subscriptions.get(subscription_id)
        if not entry:
            return False

        with Session(engine) as session:
            db_sub = session.get(Subscription, subscription_id)
            if db_sub:
                session.delete(db_sub)
                session.commit()

        self._remove_from_indices(entry)
        logger.info("Removed subscription %s", subscription_id)
        return True

    def get(self, subscription_id: str) -> SubscriptionEntry | None:
        """Get subscription by ID."""
        return self._subscriptions.get(subscription_id)

    def get_all(self) -> list[SubscriptionEntry]:
        """Get all subscriptions."""
        return list(self._subscriptions.values())

    def get_by_cell(self, cell_id: int) -> list[SubscriptionEntry]:
        """Get all subscriptions for a cell."""
        sub_ids = self._by_cell.get(cell_id, set())
        return [
            self._subscriptions[sid] for sid in sub_ids if sid in self._subscriptions
        ]

    def get_by_cell_event(
        self, cell_id: int, event_type: str
    ) -> list[SubscriptionEntry]:
        """Get subscriptions for a specific cell and event type."""
        sub_ids = self._by_cell_event.get((cell_id, event_type), set())
        return [
            self._subscriptions[sid] for sid in sub_ids if sid in self._subscriptions
        ]

    def cleanup_expired(self) -> int:
        """Remove expired subscriptions. Returns count of removed."""
        now = datetime.now()
        expired_ids: list[str] = []

        with Session(engine) as session:
            subs = session.exec(
                select(Subscription).where(Subscription.expiry_time < now)
            ).all()
            for sub in subs:
                expired_ids.append(sub.id)
                session.delete(sub)
            if expired_ids:
                session.commit()

        # Remove from memory
        for sid in expired_ids:
            entry = self._subscriptions.get(sid)
            if entry:
                self._remove_from_indices(entry)

        if expired_ids:
            logger.info("Cleaned up %d expired subscriptions", len(expired_ids))

        return len(expired_ids)
