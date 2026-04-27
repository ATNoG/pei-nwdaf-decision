"""Subscription runtime for in-memory subscription management.

Loads subscriptions from SQLite on startup. Subscriptions are matched against
incoming tags using a partial-filter approach: a subscription matches if every
field in its tags_filter appears in the incoming tags with the same value.
"""

import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from src.core.database import engine
from src.models import Subscription, SubscriptionEntry
from src.models.schemas import TagsFilter

logger = logging.getLogger(__name__)


class SubscriptionRuntime:
    """Manages subscriptions in memory with DB persistence."""

    __slots__ = ("_subscriptions",)

    def __init__(self):
        self._subscriptions: dict[str, SubscriptionEntry] = {}

    def load_from_db(self) -> None:
        """Load all subscriptions from database into memory."""
        now = datetime.now()

        with Session(engine) as session:
            subs = session.exec(select(Subscription)).all()

            loaded = 0
            expired = 0
            for sub in subs:
                if sub.expiry_time < now:
                    session.delete(sub)
                    expired += 1
                    continue

                entry = SubscriptionEntry(
                    id=sub.id,
                    callback_url=sub.callback_url,
                    tags_filter=TagsFilter(**sub.tags_filter),
                    event_types=sub.event_types,
                    created_at=sub.created_at,
                )
                if entry.id:
                    self._subscriptions[entry.id] = entry
                loaded += 1

            if expired > 0:
                session.commit()
                logger.info("Cleaned up %d expired subscriptions", expired)

        logger.info("Loaded %d subscriptions from database", loaded)

    def add(self, entry: SubscriptionEntry) -> SubscriptionEntry:
        """Add subscription to memory and persist to DB."""
        with Session(engine) as session:
            db_sub = Subscription(
                callback_url=entry.callback_url,
                tags_filter=entry.tags_filter.to_match_dict(),
                event_types=entry.event_types,
            )
            session.add(db_sub)
            session.commit()
            session.refresh(db_sub)

            entry.id = db_sub.id
            entry.created_at = db_sub.created_at

        self._subscriptions[entry.id] = entry
        logger.info("Added subscription %s for tags_filter %s", entry.id, entry.tags_filter)
        return entry

    def remove(self, subscription_id: str) -> bool:
        """Remove subscription from memory and DB."""
        entry = self._subscriptions.pop(subscription_id, None)
        if not entry:
            return False

        with Session(engine) as session:
            db_sub = session.get(Subscription, subscription_id)
            if db_sub:
                session.delete(db_sub)
                session.commit()

        logger.info("Removed subscription %s", subscription_id)
        return True

    def get(self, subscription_id: str) -> SubscriptionEntry | None:
        """Get subscription by ID."""
        return self._subscriptions.get(subscription_id)

    def get_all(self) -> list[SubscriptionEntry]:
        """Get all subscriptions."""
        return list(self._subscriptions.values())

    def get_matching(self, tags: dict, event: str | None = None) -> list[SubscriptionEntry]:
        """Return subscriptions whose tags_filter is a subset of incoming tags.

        A subscription matches if every non-None field in its tags_filter equals the
        corresponding field in the incoming tags. An empty event_types list means
        subscribe to all events.
        """
        results = []
        for entry in self._subscriptions.values():
            filter_dict = entry.tags_filter.to_match_dict()
            if not filter_dict:
                continue
            if not all(tags.get(k) == v for k, v in filter_dict.items()):
                continue
            if event and entry.event_types and event not in entry.event_types:
                continue
            results.append(entry)
        return results

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

        for sid in expired_ids:
            self._subscriptions.pop(sid, None)

        if expired_ids:
            logger.info("Cleaned up %d expired subscriptions", len(expired_ids))

        return len(expired_ids)
