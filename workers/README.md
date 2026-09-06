# EduVijna workers

Cursor A owns Celery workers for asynchronous identity extraction, answer-region
mapping, and rubric evaluation jobs.

Redis is the local broker and result backend. Task implementations will call the
typed operations in `ai/`; they must remain tenant-scoped, idempotent, and safe
to retry. This package is intentionally only a bootstrap stub.
