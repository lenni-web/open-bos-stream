"""Push-Benachrichtigungen an angemeldete Geräte (PWA, Browser).

Jedes Konto meldet seine Geräte selbst an und wählt die Ereignisse. Beim
Versand wird pro Gerät neu geprüft, ob das Konto die betroffene Quelle noch
sehen darf; serverweite Störungen gehen nur an Kreis-Admins und
Superadmins. Der Versand läuft wie bei E-Mail in einem eigenen Thread.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from pathlib import Path

import requests
from sqlalchemy import delete, select, update

from open_bos_stream.auth.guest_access import can_see_source
from open_bos_stream.core.installation import server_access_settings
from open_bos_stream.db.schema import PUSH_EVENTS, push_subscriptions
from open_bos_stream.notifications import webpush
from open_bos_stream.notifications.monitor import Notice
from open_bos_stream.org.service import now_iso

logger = logging.getLogger(__name__)

QUEUE_LIMIT = 50
MAX_DEVICES_PER_USER = 10


class PushError(ValueError):
    """Ungültige Anmeldung eines Geräts."""


def may_receive_server_events(user: dict) -> bool:
    return user.get("role") == "superadmin" or bool(user.get("server_admin")) or (
        # Ältere, vereinfachte Konten ohne Organisationsdaten.
        "org_view" not in user and user.get("role") in ("admin", "superadmin")
    )


def available_events(user: dict) -> dict[str, str]:
    """Ereignisse, die dieses Konto abonnieren darf (Schlüssel → Text)."""

    server = may_receive_server_events(user)
    return {
        key: label
        for key, (label, scope) in PUSH_EVENTS.items()
        if scope == "source" or server
    }


class PushService:
    def __init__(
        self,
        config,
        auth_service,
        key_file: str | Path = "config/webpush.key",
        post=requests.post,
    ) -> None:
        self._config = config
        self._auth = auth_service
        self._key_file = Path(key_file)
        self._post = post
        self._vapid: webpush.VapidKey | None = None
        self._queue: queue.Queue[Notice] = queue.Queue(maxsize=QUEUE_LIMIT)
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Schlüssel und Datenbank
    # ------------------------------------------------------------------

    @property
    def vapid(self) -> webpush.VapidKey:
        with self._lock:
            if self._vapid is None:
                self._vapid = webpush.VapidKey.load_or_create(self._key_file)
            return self._vapid

    @property
    def public_key(self) -> str:
        return self.vapid.public_key

    @property
    def _engine(self):
        return self._auth.ready().db.engine

    @staticmethod
    def _row(row) -> dict:
        item = dict(row._mapping)
        try:
            item["events"] = [
                event for event in json.loads(item.get("events") or "[]")
                if event in PUSH_EVENTS
            ]
        except ValueError:
            item["events"] = []
        return item

    def subscriptions(self, user_id: int | None = None) -> list[dict]:
        query = select(push_subscriptions).order_by(push_subscriptions.c.id)
        if user_id is not None:
            query = query.where(push_subscriptions.c.user_id == user_id)
        with self._engine.connect() as connection:
            return [self._row(row) for row in connection.execute(query)]

    def subscription(self, subscription_id: int) -> dict | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                select(push_subscriptions).where(
                    push_subscriptions.c.id == subscription_id
                )
            ).first()
        return self._row(row) if row else None

    @staticmethod
    def _clean_events(user: dict, events) -> list[str]:
        allowed = available_events(user)
        if events is None:
            return list(allowed)
        return [event for event in dict.fromkeys(events) if event in allowed]

    def subscribe(
        self,
        user: dict,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
        label: str = "",
        events=None,
        replaces: str | None = None,
    ) -> dict:
        """Gerät anmelden oder die Anmeldung aktualisieren.

        Ohne ``events`` bleiben die bisherigen Ereignisse erhalten (bzw. die
        des ersetzten Abos); ein neues Gerät erhält alle erlaubten.
        """

        endpoint = str(endpoint or "").strip()
        if len(endpoint) > 1000 or not webpush.endpoint_allowed(endpoint):
            raise PushError(
                "Dieser Browser nutzt einen unbekannten Push-Dienst."
            )
        if not webpush.valid_client_keys(p256dh, auth):
            raise PushError("Die Schlüssel des Geräts sind ungültig.")
        values = {
            "user_id": user["user_id"],
            "p256dh": p256dh.strip(),
            "auth": auth.strip(),
            "last_error": "",
        }
        if label:
            values["label"] = str(label).strip()[:80]
        if events is not None:
            values["events"] = json.dumps(self._clean_events(user, events))
        with self._engine.begin() as connection:
            existing = connection.execute(
                select(push_subscriptions.c.id, push_subscriptions.c.user_id).where(
                    push_subscriptions.c.endpoint == endpoint
                )
            ).first()
            previous = None
            if replaces and replaces != endpoint:
                previous = connection.execute(
                    select(push_subscriptions).where(
                        push_subscriptions.c.endpoint == str(replaces),
                        push_subscriptions.c.user_id == user["user_id"],
                    )
                ).first()
            if previous is not None:
                values.setdefault("events", previous.events)
                values.setdefault("label", previous.label)
                connection.execute(
                    delete(push_subscriptions).where(
                        push_subscriptions.c.id == previous.id
                    )
                )
            if existing and existing.user_id != user["user_id"]:
                # Anderes Konto auf demselben Gerät: Auswahl neu beginnen.
                values.setdefault(
                    "events", json.dumps(self._clean_events(user, None))
                )
            if existing:
                # Dasselbe Gerät, ggf. jetzt mit einem anderen Konto.
                connection.execute(
                    update(push_subscriptions)
                    .where(push_subscriptions.c.id == existing.id)
                    .values(**values)
                )
                subscription_id = existing.id
            else:
                count = len(
                    connection.execute(
                        select(push_subscriptions.c.id).where(
                            push_subscriptions.c.user_id == user["user_id"]
                        )
                    ).all()
                )
                if count >= MAX_DEVICES_PER_USER:
                    raise PushError(
                        f"Höchstens {MAX_DEVICES_PER_USER} Geräte je Konto. "
                        "Bitte zuerst ein altes Gerät entfernen."
                    )
                values.setdefault(
                    "events", json.dumps(self._clean_events(user, None))
                )
                values.setdefault("label", "")
                subscription_id = connection.execute(
                    push_subscriptions.insert().values(
                        endpoint=endpoint,
                        created_at=now_iso(),
                        **values,
                    )
                ).inserted_primary_key[0]
        return self.subscription(subscription_id)

    def update_events(self, user: dict, subscription_id: int, events) -> dict:
        self._own(user, subscription_id)
        with self._engine.begin() as connection:
            connection.execute(
                update(push_subscriptions)
                .where(push_subscriptions.c.id == subscription_id)
                .values(events=json.dumps(self._clean_events(user, events)))
            )
        return self.subscription(subscription_id)

    def unsubscribe(self, user: dict, subscription_id: int) -> None:
        self._own(user, subscription_id)
        self._delete(subscription_id)

    def _own(self, user: dict, subscription_id: int) -> dict:
        item = self.subscription(subscription_id)
        if not item or item["user_id"] != user.get("user_id"):
            raise LookupError("Gerät nicht gefunden.")
        return item

    def _delete(self, subscription_id: int) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                delete(push_subscriptions).where(
                    push_subscriptions.c.id == subscription_id
                )
            )

    def _mark(self, subscription_id: int, *, error: str = "") -> None:
        values = {"last_error": error[:200]}
        if not error:
            values["last_success_at"] = now_iso()
        with self._engine.begin() as connection:
            connection.execute(
                update(push_subscriptions)
                .where(push_subscriptions.c.id == subscription_id)
                .values(**values)
            )

    # ------------------------------------------------------------------
    # Empfänger und Versand
    # ------------------------------------------------------------------

    def _may_receive(self, user: dict, notice: Notice) -> bool:
        entry = PUSH_EVENTS.get(notice.event)
        if entry is None:
            return False
        if entry[1] == "server":
            return may_receive_server_events(user)
        if notice.source_id is None:
            return True
        source = next(
            (
                item for item in self._config.sources
                if str(item.id) == str(notice.source_id)
            ),
            None,
        )
        if source is None:
            # Quelle inzwischen entfernt: nur an Konten ohne Einschränkung.
            return may_receive_server_events(user)
        return can_see_source(user, source)

    def recipients(self, notice: Notice) -> list[dict]:
        """Abos, die diese Meldung erhalten (Rechte werden neu geprüft)."""

        users: dict[int, dict | None] = {}
        selected = []
        for item in self.subscriptions():
            if notice.event not in item["events"]:
                continue
            user_id = item["user_id"]
            if user_id not in users:
                users[user_id] = self._auth.session_user_for(user_id)
            user = users[user_id]
            if user and self._may_receive(user, notice):
                selected.append(item)
        return selected

    @staticmethod
    def _subject() -> str:
        settings = server_access_settings()
        domain = settings.get("public_domain") or ""
        if domain:
            return f"https://{domain}"
        # Apple verlangt eine Kontaktangabe; ohne Domain ein Platzhalter.
        return "mailto:webpush@open-bos.invalid"

    @staticmethod
    def message(notice: Notice) -> dict:
        body = notice.body.split("\n\n", 1)[0]
        if len(body) > 600:
            body = body[:597] + "…"
        return {
            "title": notice.subject,
            "body": body,
            # Entwarnung ersetzt auf dem Gerät die Störungsmeldung.
            "tag": f"{notice.event}:{notice.source_id or ''}",
            "url": "/",
            "recovery": notice.recovery,
        }

    def deliver(self, notice: Notice, targets: list[dict] | None = None) -> dict:
        """Meldung sofort an die Geräte senden (im Hintergrund-Thread)."""

        targets = self.recipients(notice) if targets is None else targets
        message = self.message(notice)
        subject = self._subject()
        result = {"sent": 0, "failed": 0, "removed": 0, "errors": []}
        for item in targets:
            try:
                webpush.send(
                    self._post,
                    self.vapid,
                    item,
                    message,
                    subject=subject,
                    urgency="normal" if notice.recovery else "high",
                )
            except webpush.WebPushError as exc:
                if exc.gone:
                    self._delete(item["id"])
                    result["removed"] += 1
                    continue
                self._mark(item["id"], error=str(exc))
                result["failed"] += 1
                result["errors"].append(str(exc))
                logger.warning(
                    "Push an Gerät %s nicht zugestellt: %s", item["id"], exc
                )
            else:
                self._mark(item["id"])
                result["sent"] += 1
        return result

    def send_test(self, user: dict) -> dict:
        devices = self.subscriptions(user["user_id"])
        if not devices:
            raise PushError("Für dieses Konto ist noch kein Gerät angemeldet.")
        return self.deliver(
            Notice(
                event="test",
                subject="Testbenachrichtigung",
                body=(
                    "Push-Benachrichtigungen von Open BOS Drohnen kommen "
                    "auf diesem Gerät an."
                ),
            ),
            targets=devices,
        )

    def enqueue(self, notice: Notice) -> bool:
        if notice.event not in PUSH_EVENTS:
            return False
        try:
            self._queue.put_nowait(notice)
        except queue.Full:
            logger.warning("Push verworfen, Warteschlange voll: %s", notice.subject)
            return False
        self._ensure_worker()
        return True

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run,
                name="open-bos-push",
                daemon=True,
            )
            self._worker.start()

    def _run(self) -> None:
        while True:
            notice = self._queue.get()
            try:
                result = self.deliver(notice)
                if result["sent"] or result["failed"]:
                    logger.info(
                        "Push „%s“: %s zugestellt, %s fehlgeschlagen.",
                        notice.subject,
                        result["sent"],
                        result["failed"],
                    )
            except Exception:
                logger.exception("Push-Versand fehlgeschlagen.")
            finally:
                self._queue.task_done()
