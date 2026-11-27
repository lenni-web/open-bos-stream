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
