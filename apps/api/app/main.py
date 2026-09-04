from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.middleware.correlation import CorrelationIdMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(title="EduVijna Paper Evaluation API", version=settings.api_version)
    application.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(application)
    application.include_router(api_router)
    return application


app = create_app()
