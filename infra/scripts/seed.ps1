$ErrorActionPreference = "Stop"
docker compose exec api python -m app.cli.seed_dev
