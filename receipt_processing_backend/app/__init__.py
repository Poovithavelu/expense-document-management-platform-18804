from flask import Flask
from flask_cors import CORS
from flask_smorest import Api
from .routes.health import blp as health_blp
from .routes.api import blp as api_blp
from .config import Config
from .models import db


app = Flask(__name__)
app.url_map.strict_slashes = False

# Load configuration
cfg = Config()
app.config["API_TITLE"] = cfg.API_TITLE
app.config["API_VERSION"] = cfg.API_VERSION
app.config["OPENAPI_VERSION"] = cfg.OPENAPI_VERSION
app.config["OPENAPI_URL_PREFIX"] = cfg.OPENAPI_URL_PREFIX
app.config["OPENAPI_SWAGGER_UI_PATH"] = cfg.OPENAPI_SWAGGER_UI_PATH
app.config["OPENAPI_SWAGGER_UI_URL"] = cfg.OPENAPI_SWAGGER_UI_URL

# Database
app.config["SQLALCHEMY_DATABASE_URI"] = cfg.SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = cfg.SQLALCHEMY_TRACK_MODIFICATIONS
app.config["UPLOAD_DIR"] = cfg.UPLOAD_DIR

CORS(app, resources={r"/*": {"origins": "*"}})

# Init extensions
db.init_app(app)

with app.app_context():
    # Ensure DB tables exist (for demo; in production use migrations)
    db.create_all()

api = Api(app)
api.register_blueprint(health_blp)
api.register_blueprint(api_blp)
