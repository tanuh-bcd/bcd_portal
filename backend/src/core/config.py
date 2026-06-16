import os
import urllib.parse
from dotenv import load_dotenv
from .secrets import get_secret

load_dotenv()


def _cfg(name: str, default: str = "") -> str:
    return os.getenv(name) or get_secret(name, default)


class Settings:
    PROJECT_NAME: str = "Tanuh BCD API"
    PROJECT_VERSION: str = "1.0.0"

    MYSQL_USER: str = _cfg("MYSQL_USER")
    MYSQL_PASSWORD: str = _cfg("MYSQL_PASSWORD")
    MYSQL_HOST: str = _cfg("MYSQL_HOST")
    MYSQL_PORT: str = _cfg("MYSQL_PORT", "3306")
    MYSQL_DB: str = _cfg("MYSQL_DB")
    MYSQL_QUERY: str = _cfg("MYSQL_QUERY")
    MYSQL_SSL_CA: str = _cfg("MYSQL_SSL_CA")
    MYSQL_SSL_CERT: str = _cfg("MYSQL_SSL_CERT")
    MYSQL_SSL_KEY: str = _cfg("MYSQL_SSL_KEY")

    @property
    def DATABASE_URL(self) -> str:
        password = urllib.parse.quote_plus(self.MYSQL_PASSWORD) if self.MYSQL_PASSWORD else ""
        url = f"mysql+pymysql://{self.MYSQL_USER}:{password}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        if self.MYSQL_QUERY:
            url += f"?{self.MYSQL_QUERY}"
        return url

    SECRET_KEY: str = _cfg("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    GCP_STORAGE_BUCKET: str = _cfg("GCP_STORAGE_BUCKET")

    CLOUD_SQL_CONNECTION_NAME: str = _cfg("CLOUD_SQL_CONNECTION_NAME")
    USE_CLOUD_SQL_CONNECTOR: bool = _cfg("USE_CLOUD_SQL_CONNECTOR", "false").lower() == "true"

    SMTP_HOST: str = _cfg("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(_cfg("SMTP_PORT", "587"))
    SMTP_USER: str = _cfg("SMTP_USER")
    SMTP_PASSWORD: str = _cfg("SMTP_PASSWORD")
    SMTP_FROM: str = _cfg("SMTP_FROM")

    MYSQL_DB_QUESTIONNAIRE: str = _cfg("MYSQL_DB_QUESTIONNAIRE", "bcd_questionnaire")

settings = Settings()
