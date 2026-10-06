import os
from dotenv import load_dotenv


load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # ---- MySQL connection ----
    MYSQL_USER = os.environ.get("MYSQL_USER")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
    MYSQL_HOST = os.environ.get("MYSQL_HOST")
    MYSQL_PORT = os.environ.get("MYSQL_PORT")
    MYSQL_DB = os.environ.get("MYSQL_DB", "personal_document_manager")

    # DATABASE_URL lets the tests run on an in-memory SQLite database instead of MySQL
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- File upload ----
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB per request
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

    # ---- Storage quotas ----
    USER_QUOTA_BYTES = 20 * 1024 * 1024 * 1024       # 20 GB / user
    ADMIN_TOTAL_QUOTA_BYTES = 500 * 1024 * 1024 * 1024  # 500 GB total
