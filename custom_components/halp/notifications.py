"""Change-aware persistent notification publishing for HALP!.

Keep one publisher per running HALP! config entry. It remembers the last
published title/message for each stable notification ID, so the periodic
configuration checks do not generate redundant Home Assistant service calls.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class NotificationPublisher:
    """Publish/dismiss a notice only when its expected state changes.

    A manually dismissed notification remains dismissed for the remainder
    of this entry's runtime while its expected content is unchanged. An
    actual message change can publish it again. After reload/restart the
    per-entry cache is rebuilt, so outstanding problems can be shown once.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._published: dict[str, tuple[str, str] | None] = {}
        self._lock = asyncio.Lock()

    async def async_publish(self, notification_id: str, title: str, message: str) -> None:
        """Create or update a notification only if its text has changed."""
        content = (title, message)
        async with self._lock:
            if self._published.get(notification_id) == content:
                return
            await self._hass.services.async_call(
                "persistent_notification",
                "create",
                {"notification_id": notification_id, "title": title, "message": message},
                blocking=True,
            )
            self._published[notification_id] = content

    async def async_dismiss(self, notification_id: str) -> None:
        """Dismiss once when healthy, including stale notices after reload.

        A first-time dismissal intentionally reconciles notices created by
        earlier HALP! versions or a previous run, even if no local state is
        known. Subsequent healthy checks have no service calls.
        """
        async with self._lock:
            if notification_id in self._published and self._published[notification_id] is None:
                return
            await self._hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": notification_id},
                blocking=True,
            )
            self._published[notification_id] = None
