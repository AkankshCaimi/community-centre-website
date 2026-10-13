from flask import Flask

from app.api.health import bp as health_bp
from app.config import Config


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(health_bp)
    return app
