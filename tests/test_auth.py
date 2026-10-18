from project.models import db, User


class TestRegisterUser:

    def test_should_store_new_user_account(self, app):
        # Create a new client
        guest = app.test_client()

        # Submit the registration form
        response = guest.post(
            "/register",
            data={
                "username": "autumn",
                "email": "autumn@example.com",
                "password": "test123",
            },
        )

        # Registration redirects to login
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

        # Check that the account details were saved
        saved_user = User.query.filter_by(username="autumn").first()

        assert saved_user is not None
        assert saved_user.email == "autumn@example.com"
        assert saved_user.role == "user"

        # Check that the password is hashed and works
        assert saved_user.password_hash
        assert saved_user.password_hash != "test123"
        assert saved_user.check_password("test123")
        assert not saved_user.check_password("wrongpassword")

    def test_should_reject_missing_required_fields(self, app):
        guest = app.test_client()
        count_before = User.query.count()

        response = guest.post(
            "/register",
            data={
                "username": "",
                "email": "autumn@example.com",
                "password": "test123",
            },
        )

        assert response.status_code == 200
        assert b"Please fill in all fields." in response.data
        assert User.query.count() == count_before

    def test_should_reject_short_password(self, app):
        guest = app.test_client()
        count_before = User.query.count()

        response = guest.post(
            "/register",
            data={
                "username": "newuser",
                "email": "new@example.com",
                "password": "12345",
            },
        )

        assert response.status_code == 200
        assert b"Password must be at least 6 characters." in response.data
        assert User.query.count() == count_before

    def test_should_reject_duplicate_username(self, app, user):
        guest = app.test_client()
        count_before = User.query.count()

        response = guest.post(
            "/register",
            data={
                "username": user.username,
                "email": "different@example.com",
                "password": "secret123",
            },
        )

        assert response.status_code == 200
        assert b"This username is already taken." in response.data
        assert User.query.count() == count_before

    def test_should_reject_duplicate_email(self, app, user):
        guest = app.test_client()
        count_before = User.query.count()

        response = guest.post(
            "/register",
            data={
                "username": "differentuser",
                "email": user.email,
                "password": "secret123",
            },
        )

        assert response.status_code == 200
        assert b"This email is already registered." in response.data
        assert User.query.count() == count_before


class TestLoginUser:

    def test_should_login_with_valid_credentials(self, app, user):
        # Create a client that is not already logged in
        guest = app.test_client()

        response = guest.post(
            "/login",
            data={
                "username": user.username,
                "password": "secret123",
            },
        )

        # Check the redirect
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

        # Check that login created the correct session
        with guest.session_transaction() as session:
            assert session["user_id"] == user.id
            assert session["username"] == user.username
            assert session["role"] == "user"

        # Check that the logged-in client can access the dashboard
        dashboard_response = guest.get("/dashboard")
        assert dashboard_response.status_code == 200

    def test_should_reject_incorrect_password(self, app, user):
        guest = app.test_client()

        response = guest.post(
            "/login",
            data={
                "username": user.username,
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 200
        assert b"Incorrect username or password." in response.data

        with guest.session_transaction() as session:
            assert "user_id" not in session

        response = guest.get("/dashboard")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_should_reject_unknown_username(self, app):
        guest = app.test_client()

        response = guest.post(
            "/login",
            data={
                "username": "nonexistent",
                "password": "secret123",
            },
        )

        assert response.status_code == 200
        assert b"Incorrect username or password." in response.data

        with guest.session_transaction() as session:
            assert "user_id" not in session

        response = guest.get("/dashboard")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_should_reject_empty_credentials(self, app):
        guest = app.test_client()

        response = guest.post(
            "/login",
            data={"username": "", "password": ""},
        )

        assert response.status_code == 200
        assert b"Incorrect username or password." in response.data

        with guest.session_transaction() as session:
            assert "user_id" not in session

        response = guest.get("/dashboard")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_should_reject_deactivated_account(self, app, user):
        guest = app.test_client()

        # Deactivate the existing account before attempting login
        user.is_active_account = False
        db.session.commit()

        response = guest.post(
            "/login",
            data={
                "username": user.username,
                "password": "secret123",
            },
        )

        assert response.status_code == 200
        assert (
            b"This account has been deactivated. "
            b"Please contact an administrator."
        ) in response.data

        with guest.session_transaction() as session:
            assert "user_id" not in session

        response = guest.get("/dashboard")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


class TestLogoutUser:

    def test_should_logout_successfully(self, client):
        # Confirm the client is logged in before logout
        with client.session_transaction() as session:
            assert "user_id" in session

        response = client.get("/logout")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

        # Check that the login details were removed
        with client.session_transaction() as session:
            assert "user_id" not in session
            assert "username" not in session
            assert "role" not in session

        # The user should no longer have dashboard access
        response = client.get("/dashboard")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_should_handle_logout_when_not_logged_in(self, app):
        guest = app.test_client()

        response = guest.get("/logout")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

        with guest.session_transaction() as session:
            assert "user_id" not in session
            assert "username" not in session
            assert "role" not in session