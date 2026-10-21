import os
import logging
from flask import Flask
from app.config import Config
from app.database import db_session, init_db
from app.services.seed_service import seed_defaults

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("qr_attendance")

def create_app(config_class=Config):
    """Application Factory Pattern for production Flask deployment."""
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )
    app.config.from_object(config_class)

    # Register Blueprints
    from app.routes.public import public_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    # Session teardown
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    # Initialize Database & Seed
    with app.app_context():
        init_db()
        seed_defaults()

    return app
