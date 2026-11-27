"""Tabellen für Organisationen, Konten, Mitgliedschaften und Nachweise."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
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

# Rollen in einer Organisation (aufsteigend).
MEMBERSHIP_ROLES = {
    "viewer": "Zuschauer",
    "operator": "Drohnenteam",
    "admin": "Wehr-Admin",
}

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
    UniqueConstraint("user_id", "organization_id", name="uq_membership"),
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
    "source_offline": ("Quelle ohne Signal", "source"),
    "recording_problem": ("Aufnahme abgebrochen oder fehlgeschlagen", "source"),
    "mediamtx_offline": ("Streaming-Server gestört", "server"),
    "output_failed": ("Streaming-Ausgang unerwartet beendet", "server"),
    "storage_low": ("Speicher wird knapp", "server"),
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
)

incident_organizations = Table(
    "incident_organizations",
    metadata,
    Column(
        "incident_id",
        Integer,
        ForeignKey("incidents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "organization_id",
        Integer,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("added_at", String(32), nullable=False),
    Column("added_by", String(80), nullable=False, default=""),
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
