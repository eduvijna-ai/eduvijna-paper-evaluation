.PHONY: bootstrap up down reset migrate test lint typecheck verify logs ps

# Unix/macOS: make <target>
# Windows PowerShell equivalents: infra/scripts/<target>.ps1

bootstrap:
	@if [ -f infra/scripts/bootstrap.sh ]; then sh infra/scripts/bootstrap.sh; else powershell -File infra/scripts/bootstrap.ps1; fi

up:
	@if [ -f infra/scripts/up.sh ]; then sh infra/scripts/up.sh; else powershell -File infra/scripts/up.ps1; fi

down:
	@if [ -f infra/scripts/down.sh ]; then sh infra/scripts/down.sh; else powershell -File infra/scripts/down.ps1; fi

reset:
	@if [ -f infra/scripts/reset-local.sh ]; then sh infra/scripts/reset-local.sh; else powershell -File infra/scripts/reset-local.ps1; fi

migrate:
	@if [ -f infra/scripts/migrate.sh ]; then sh infra/scripts/migrate.sh; else powershell -File infra/scripts/migrate.ps1; fi

test:
	@if [ -f infra/scripts/test.sh ]; then sh infra/scripts/test.sh; else powershell -File infra/scripts/test.ps1; fi

lint:
	@if [ -f infra/scripts/lint.sh ]; then sh infra/scripts/lint.sh; else powershell -File infra/scripts/lint.ps1; fi

typecheck:
	@if [ -f infra/scripts/typecheck.sh ]; then sh infra/scripts/typecheck.sh; else powershell -File infra/scripts/typecheck.ps1; fi

verify:
	@if [ -f infra/scripts/verify.sh ]; then sh infra/scripts/verify.sh; else powershell -File infra/scripts/verify.ps1; fi

logs:
	docker compose logs -f

ps:
	docker compose ps
