"""Alembic-Umgebung: nutzt die Verbindung von Database.migrate()."""

from alembic import context

from open_bos_stream.db.schema import metadata


connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Migrationen laufen nur über Database.migrate().")

context.configure(
    connection=connection,
    target_metadata=metadata,
    render_as_batch=True,
)
with context.begin_transaction():
    context.run_migrations()
