# Sycamore G3 ingest service
# Polls GDELT DOC 2.0 every 15 min, normalizes to the shared event schema,
# writes public/data/events.json + manifest.json. Run as a user-level systemd
# timer (see g3-ingest/systemd/).
