import os

import pytest

# Use an in-memory SQLite database for tests, so they never touch the real MySQL database.
# These must be set before the project is imported, because config.py reads them on import.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from project.app import app as flask_app, facade  # noqa: E402
from project.models import db, User, Document  # noqa: E402


@pytest.fixture
def app(tmp_path):
    # Show the 500 error page instead of raising the error inside the test
    flask_app.config["PROPAGATE_EXCEPTIONS"] = False
    # Save uploaded files in a temporary folder, not in the project folder
    facade.storage.upload_folder = str(tmp_path)

    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


def make_user(username):
    user = User(username=username, email=f"{username}@example.com", role="user")
    user.set_password("secret123")
    db.session.add(user)
    db.session.commit()
    return user


def make_document(user, upload_folder, title="Report"):
    folder = os.path.join(upload_folder, str(user.id))
    os.makedirs(folder, exist_ok=True)
    stored_filename = f"{title.lower()}_stored.txt"
    with open(os.path.join(folder, stored_filename), "w", encoding="utf-8") as f:
        f.write("hello world")

    doc = Document(
        user_id=user.id,
        version=1,
        title=title,
        category="Work",
        notes="",
        original_filename=f"{title.lower()}.txt",
        stored_filename=stored_filename,
        filesize_bytes=11,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


@pytest.fixture
def user(app):
    return make_user("alice")


@pytest.fixture
def other_user(app):
    return make_user("bob")


@pytest.fixture
def document(user):
    return make_document(user, facade.storage.upload_folder)


@pytest.fixture
def other_document(other_user):
    return make_document(other_user, facade.storage.upload_folder, title="Secret")


@pytest.fixture
def client(app, user):
    # A test client that is already logged in as "alice"
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = user.role
    return client
