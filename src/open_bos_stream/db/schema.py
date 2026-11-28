"""Tabellen für Organisationen, Konten, Mitgliedschaften und Nachweise."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)


metadata = MetaData()

# Arten im Organisationsbaum (Landkreis → Stadt-/Gemeinde-/
# Samtgemeindefeuerwehr → Ortsfeuerwehr, dazu Kreiseinheiten).
ORGANIZATION_KINDS = {
    "landkreis": "Landkreis",
    "stadtfeuerwehr": "Stadtfeuerwehr",
    "gemeindefeuerwehr": "Gemeindefeuerwehr",
    "samtgemeindefeuerwehr": "Samtgemeindefeuerwehr",
    "ortsfeuerwehr": "Ortsfeuerwehr",
    "kreiseinheit": "Kreiseinheit",
}

# Unter welchen Arten eine Organisation liegen darf. Die oberste
# Organisation hat keine übergeordnete und ist davon ausgenommen.
ORGANIZATION_PARENT_KINDS = {
    "landkreis": (),
    "stadtfeuerwehr": ("landkreis",),
    "gemeindefeuerwehr": ("landkreis",),
    "samtgemeindefeuerwehr": ("landkreis",),
    "ortsfeuerwehr": (
        "landkreis",
        "stadtfeuerwehr",
        "gemeindefeuerwehr",
        "samtgemeindefeuerwehr",
    ),
    "kreiseinheit": ("landkreis",),
}

# Rollen in einer Organisation (aufsteigend).
MEMBERSHIP_ROLES = {
    "viewer": "Zuschauer",
    "operator": "Drohnenteam",
    "admin": "Wehr-Admin",
    "ortsbrandmeister": "Ortsbrandmeister",
}

# Rollen mit eigenem Titel, die die Rechte einer anderen Rolle haben.
ROLE_RIGHTS = {"ortsbrandmeister": "admin"}

# Rollen, die es nur in bestimmten Arten von Organisationen gibt.
ROLE_ORGANIZATION_KINDS = {"ortsbrandmeister": "ortsfeuerwehr"}

# Fernpilotennachweise nach EU-Drohnenverordnung.
QUALIFICATION_KINDS = {
    "a1a3": "EU-Kompetenznachweis A1/A3",
    "a2": "EU-Fernpilotenzeugnis A2",
    "sts": "STS-Zeugnis (Standardszenario)",
    "other": "Sonstiger Nachweis",
}

organizations = Table(
    "organizations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(120), nullable=False),
    Column("short_name", String(40), nullable=False, default=""),
    Column("kind", String(40), nullable=False),
    Column(
        "parent_id",
        Integer,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    Column("latitude", Float, nullable=True),
    Column("longitude", Float, nullable=True),
    Column("archived", Boolean, nullable=False, default=False),
    Column("created_at", String(32), nullable=False),
)

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String(32), nullable=False, unique=True),
    Column("display_name", String(80), nullable=False, default=""),
    # Seit 0.25.4: Name getrennt; display_name = „Vorname Nachname“.
    Column("first_name", String(60), nullable=False, default=""),
    Column("last_name", String(60), nullable=False, default=""),
    Column("nickname", String(40), nullable=False, default=""),
    Column("email", String(254), nullable=False, default=""),
    Column("password_hash", Text, nullable=False),
    Column("platform_admin", Boolean, nullable=False, default=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", String(32), nullable=False),
    Column("last_login_at", String(32), nullable=True),
)

memberships = Table(
    "memberships",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "organization_id",
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("role", String(16), nullable=False),
    # Seit 0.26.3 sind mehrere Rollen je Organisation möglich.
    UniqueConstraint("user_id", "organization_id", "role", name="uq_membership_role"),
)

qualifications = Table(
    "qualifications",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("kind", String(16), nullable=False),
    Column("reference", String(80), nullable=False, default=""),
    Column("valid_until", Date, nullable=True),
    Column("note", String(200), nullable=False, default=""),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("at", String(32), nullable=False),
    Column("actor", String(80), nullable=False, default=""),
    Column("action", String(60), nullable=False),
    Column("target", String(200), nullable=False, default=""),
    Column("organization_id", Integer, nullable=True),
)

# Ereignisse, die ein Gerät per Web Push abonnieren kann. ``scope`` legt
# fest, wer sie erhält: "source" = wer die Quelle sehen darf,
# "server" = nur Kreis-Admins und Superadmins (serverweite Störungen).
PUSH_EVENTS = {
    "incident_started": ("Neuer Einsatz (eigene oder beteiligte Wehr)", "incident"),
    "source_offline": ("Drohne ohne Signal", "source"),
    "recording_problem": ("Aufnahme abgebrochen oder fehlgeschlagen", "source"),
    "mediamtx_offline": ("Streaming-Server gestört", "server"),
    "output_failed": ("Streaming-Ausgang unerwartet beendet", "server"),
    "storage_low": ("Speicher wird knapp", "server"),
    "server_load": ("Server überlastet", "server"),
    "server_started": ("Server neu gestartet", "server"),
}

push_subscriptions = Table(
    "push_subscriptions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("endpoint", String(1000), nullable=False, unique=True),
    Column("p256dh", String(120), nullable=False),
    Column("auth", String(40), nullable=False),
    Column("label", String(80), nullable=False, default=""),
    Column("events", Text, nullable=False, default="[]"),
    Column("created_at", String(32), nullable=False),
    Column("last_success_at", String(32), nullable=True),
    Column("last_error", String(200), nullable=False, default=""),
)

# ----------------------------------------------------------------------
# Einsätze (ab 0.23)
# ----------------------------------------------------------------------

INCIDENT_STATUS = {
    "running": "laufend",
    "ended": "beendet",
    "closed": "abgeschlossen",
}

# Funktion einer Person im Einsatz (Dokumentation, keine Rechte).
INCIDENT_ROLES = {
    "einsatzleiter": "Einsatzleiter",
    "abschnittsleiter_drohne": "Abschnittsleiter Drohne",
    "fernpilot": "Fernpilot",
    "luftraumbeobachter": "Luftraumbeobachter",
    "payload": "Kamera-/Payload-Operator",
    "dokumentation": "Dokumentation",
    "sonstige": "Sonstige",
}

incidents = Table(
    "incidents",
    metadata,
    Column("id", Integer, primary_key=True),
    # Kennung aus Datum und Alarmzeit, z. B. 2026-11-26-1432 (bzw. -2).
    Column("code", String(24), nullable=False, unique=True),
    Column("title", String(120), nullable=False, default=""),
    Column("keyword", String(80), nullable=False, default=""),
    Column("address", String(200), nullable=False, default=""),
    Column("latitude", Float, nullable=True),
    Column("longitude", Float, nullable=True),
    Column("alarm_at", String(32), nullable=False),
    Column("ended_at", String(32), nullable=True),
    Column("status", String(16), nullable=False, default="running"),
    Column(
        "lead_organization_id",
        Integer,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("alarm_text", Text, nullable=False, default=""),
    Column("alerted_units", String(300), nullable=False, default=""),
    Column("dispatch_number", String(40), nullable=False, default=""),
    Column("summary", Text, nullable=False, default=""),
    Column("weather", Text, nullable=True),
    Column("created_by", String(80), nullable=False, default=""),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    # Zähler für die Einsatzkarte: Jede Änderung erhöht ihn, damit alle
    # geöffneten Karten nur bei Bedarf neu laden.
    Column("map_revision", Integer, nullable=False, default=0),
    # Übung statt Realeinsatz (deutlich gekennzeichnet, eigener Bericht).
    Column("exercise", Boolean, nullable=False, default=False),
)

incident_organizations = Table(
    "incident_organizations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "incident_id",
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "organization_id",
        Integer,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("added_at", String(32), nullable=False),
    Column("added_by", String(80), nullable=False, default=""),
    # Leer: noch beteiligt. Beendete Zeiträume bleiben zur Dokumentation.
    Column("removed_at", String(32), nullable=True),
    Column("removed_by", String(80), nullable=False, default=""),
)

incident_participants = Table(
    "incident_participants",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "incident_id",
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    ),
    # Konto oder freier Name (Personen ohne Konto).
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("name", String(80), nullable=False, default=""),
    Column(
        "organization_id",
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("role", String(40), nullable=False),
    Column("from_at", String(32), nullable=True),
    Column("until_at", String(32), nullable=True),
    Column("note", String(200), nullable=False, default=""),
)

incident_sources = Table(
    "incident_sources",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "incident_id",
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("source_id", String(64), nullable=False),
    # Name zum Zeitpunkt der Zuordnung (Quelle kann später entfernt werden).
    Column("source_name", String(120), nullable=False, default=""),
    Column("added_at", String(32), nullable=False),
    Column("removed_at", String(32), nullable=True),
)

incident_log = Table(
    "incident_log",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "incident_id",
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("at", String(32), nullable=False),
    Column("actor", String(80), nullable=False, default=""),
    Column("kind", String(24), nullable=False, default="note"),
    Column("text", Text, nullable=False),
)

# Status eines Quadranten (Suchabschnitts) auf der Einsatzkarte.
MAP_ITEM_STATUS = {
    "open": "offen",
    "assigned": "zugewiesen",
    "searching": "wird abgesucht",
    "done": "abgesucht",
    "finding": "Fund / Hinweis",
}

incident_map_items = Table(
    "incident_map_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "incident_id",
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("kind", String(16), nullable=False, default="sector"),
    Column("name", String(40), nullable=False),
    # GeoJSON-Geometrie (Polygon, WGS84).
    Column("geometry", Text, nullable=False),
    Column("status", String(16), nullable=False, default="open"),
    Column("assignee", String(80), nullable=False, default=""),
    Column("note", String(300), nullable=False, default=""),
    Column("created_by", String(80), nullable=False, default=""),
    Column("created_at", String(32), nullable=False),
    Column("updated_by", String(80), nullable=False, default=""),
    Column("updated_at", String(32), nullable=False),
)

# ----------------------------------------------------------------------
# Checklisten und Dokumente (ab 0.25)
# ----------------------------------------------------------------------

CHECKLIST_STATUS = {
    "open": "offen",
    "completed": "abgeschlossen",
}

# Vorlagen pflegt der Landkreis; Positionen als JSON-Liste
# [{"section", "text", "required", "hint"}].
checklist_templates = Table(
    "checklist_templates",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "organization_id",
        Integer,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("title", String(120), nullable=False),
    Column("description", Text, nullable=False, default=""),
    Column("items", Text, nullable=False, default="[]"),
    Column("version", Integer, nullable=False, default=1),
    Column("archived", Boolean, nullable=False, default=False),
    Column("created_by", String(80), nullable=False, default=""),
    Column("created_at", String(32), nullable=False),
    Column("updated_by", String(80), nullable=False, default=""),
    Column("updated_at", String(32), nullable=False),
)

checklists = Table(
    "checklists",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("title", String(120), nullable=False),
    Column("description", Text, nullable=False, default=""),
    Column(
        "template_id",
        Integer,
        ForeignKey("checklist_templates.id", ondelete="SET NULL"),
        nullable=True,
    ),
    Column("template_version", Integer, nullable=True),
    # Wehr, der die Liste gehört (bei Einsätzen: führende Wehr beim Anlegen).
    Column(
        "organization_id",
        Integer,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "incident_id",
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column("status", String(16), nullable=False, default="open"),
    Column("created_by", String(80), nullable=False, default=""),
    Column("created_at", String(32), nullable=False),
    Column("completed_by", String(80), nullable=True),
    Column("completed_at", String(32), nullable=True),
)

checklist_items = Table(
    "checklist_items",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "checklist_id",
        Integer,
        ForeignKey("checklists.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("position", Integer, nullable=False, default=0),
    Column("section", String(80), nullable=False, default=""),
    Column("text", String(300), nullable=False),
    Column("hint", String(300), nullable=False, default=""),
    Column("required", Boolean, nullable=False, default=False),
    Column("checked", Boolean, nullable=False, default=False),
    Column("checked_by", String(80), nullable=True),
    Column("checked_at", String(32), nullable=True),
    Column("note", String(1000), nullable=False, default=""),
    Column("note_by", String(80), nullable=True),
    Column("note_at", String(32), nullable=True),
)

# Einheitliche Dokumente des Landkreises (Dateien liegen neben stream.yaml).
documents = Table(
    "documents",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "organization_id",
        Integer,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("title", String(120), nullable=False),
    Column("description", String(500), nullable=False, default=""),
    Column("stored_name", String(80), nullable=False, unique=True),
    Column("original_name", String(200), nullable=False),
    Column("content_type", String(100), nullable=False),
    Column("size", Integer, nullable=False),
    Column("uploaded_by", String(80), nullable=False, default=""),
    Column("uploaded_at", String(32), nullable=False),
)


# DJI-Geräte: Drohnen ("aircraft") und Fernsteuerungen ("controller").
dji_devices = Table(
    "dji_devices",
    metadata,
    Column("serial", String(64), primary_key=True),
    Column("kind", String(16), nullable=False),
    Column("model_type", Integer, nullable=True),
    Column("model_sub_type", Integer, nullable=True),
    Column("name", String(80), nullable=False, default=""),
    Column(
        "organization_id",
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    ),
    # Fernsteuerung, über die eine Drohne zuletzt gemeldet wurde.
    Column("gateway_serial", String(64), nullable=True),
    Column("blocked", Boolean, nullable=False, default=False),
    Column("first_seen", String(32), nullable=False),
    Column("last_seen", String(32), nullable=False),
)

# Zeitraum, in dem eine Drohne einem Einsatz zugeordnet war.
incident_drones = Table(
    "incident_drones",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "incident_id",
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("serial", String(64), nullable=False),
    # Name zum Zeitpunkt der Zuordnung (Gerät kann später entfernt werden).
    Column("name", String(80), nullable=False, default=""),
    Column("added_at", String(32), nullable=False),
    Column("removed_at", String(32), nullable=True),
)

# Jede empfangene Nachricht unverändert. Ohne Einsatz nur vorübergehend
# (Nachtragen bei späterer Zuordnung), mit Einsatz dauerhaft.
drone_records = Table(
    "drone_records",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "incident_id",
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column("serial", String(64), nullable=False),
    Column("received_at", String(32), nullable=False),
    Column("topic", String(160), nullable=False),
    # Für Flugspur und Auswertung aus der Nachricht gelesen.
    Column("latitude", Float, nullable=True),
    Column("longitude", Float, nullable=True),
    Column("elevation", Float, nullable=True),
    Column("battery", Integer, nullable=True),
    Column("home_distance", Float, nullable=True),
    Column("payload", Text, nullable=False),
    Index("ix_drone_records_incident", "incident_id", "serial", "id"),
    Index("ix_drone_records_unassigned", "serial", "received_at"),
)
