import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = "Tanuh BCD API"
    PROJECT_VERSION: str = "1.0.0"

    MYSQL_USER: str = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD")
    MYSQL_HOST: str = os.getenv("MYSQL_HOST")
    MYSQL_PORT: str = os.getenv("MYSQL_PORT", 3306)
    MYSQL_DB: str = os.getenv("MYSQL_DB")
    MYSQL_QUERY: str = os.getenv("MYSQL_QUERY", "")
    MYSQL_SSL_CA: str = os.getenv("MYSQL_SSL_CA")
    MYSQL_SSL_CERT: str = os.getenv("MYSQL_SSL_CERT")
    MYSQL_SSL_KEY: str = os.getenv("MYSQL_SSL_KEY")

    @property
    def DATABASE_URL(self) -> str:
        password = urllib.parse.quote_plus(self.MYSQL_PASSWORD) if self.MYSQL_PASSWORD else ""
        url = f"mysql+pymysql://{self.MYSQL_USER}:{password}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
        if self.MYSQL_QUERY:
            url += f"?{self.MYSQL_QUERY}"
        return url

    SECRET_KEY: str = os.getenv("SECRET_KEY") # Should be in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    GCP_STORAGE_BUCKET: str = os.getenv("GCP_STORAGE_BUCKET")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    CLOUD_SQL_CONNECTION_NAME: str = os.getenv("CLOUD_SQL_CONNECTION_NAME", "")
    USE_CLOUD_SQL_CONNECTOR: bool = os.getenv("USE_CLOUD_SQL_CONNECTOR", "false").lower() == "true"

    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")

    MYSQL_DB_QUESTIONNAIRE: str = os.getenv("MYSQL_DB_QUESTIONNAIRE", "bcd_questionnaire")

settings = Settings()
