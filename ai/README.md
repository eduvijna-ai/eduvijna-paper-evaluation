# EduVijna AI abstraction

Cursor A owns this provider-neutral package. API and Celery code call the named
operations in `provider.py`; vendor SDKs belong only in future provider adapters.

Implementations must preserve separate confidence dimensions, produce draft
evaluation proposals only, and generate reports exclusively from approved ledger
snapshots. No frontend code may hold or call provider credentials.
