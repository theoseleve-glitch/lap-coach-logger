"""Infrastructure adapters — outbound HTTP, storage, and OS integrations.

Per Block C of the 30-day desktop sprint, the ``infra`` package hosts
the new typed ingestion client (``infra.ingest.IngestClient``) and
related adapters that talk to the backend / OS. Previously these
concerns lived in ``sync/`` and ``core/``; ``infra/`` isolates them
behind typed interfaces so upstream code (finalizer, view-models)
doesn't depend on HTTP / keychain / transport details.
"""
