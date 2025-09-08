import os
from dataclasses import dataclass


@dataclass
class Config:
    """Flask configuration using environment variables.
    Ensure the following environment variables are available via .env:
    - MYSQL_URL
    - MYSQL_USER
    - MYSQL_PASSWORD
    - MYSQL_DB
    - MYSQL_PORT
    - UPLOAD_DIR (optional, defaults to instance/uploads)
    """
    API_TITLE: str = "Receipt Processing API"
    API_VERSION: str = "v1"
    OPENAPI_VERSION: str = "3.0.3"
    OPENAPI_URL_PREFIX: str = "/docs"
    OPENAPI_SWAGGER_UI_PATH: str = ""
    OPENAPI_SWAGGER_UI_URL: str = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    MYSQL_URL: str = os.getenv("MYSQL_URL", "localhost")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "documents")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    SQLALCHEMY_DATABASE_URI: str = ""
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "")

    def __post_init__(self):
        self.SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_URL}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        )
        if not self.UPLOAD_DIR:
            # Default local upload directory
            self.UPLOAD_DIR = os.path.join(os.getcwd(), "instance", "uploads")
            os.makedirs(self.UPLOAD_DIR, exist_ok=True)
