import pytest

from project.models import db, User


@pytest.fixture
def admin_user(app):
    admin = User(
        username="admin",
        email="admin@example.com",
        role="admin",
    )
    admin.set_password("secret123")
    db.session.add(admin)
    db.session.commit()
    return admin


@pytest.fixture
def admin_client(app, admin_user):
    client = app.test_client()

    with client.session_transaction() as session:
        session["user_id"] = admin_user.id
        session["username"] = admin_user.username
        session["role"] = admin_user.role

    return client


class TestAdminDashboard:

    def test_should_allow_admin_access(self, admin_client):
        response = admin_client.get("/admin")

        assert response.status_code == 200

    def test_should_reject_regular_user(self, client):
        response = client.get("/admin")

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

        with client.session_transaction() as session:
            assert (
                "error",
                "You don't have permission to access the admin dashboard.",
            ) in session.get("_flashes", [])

    def test_should_redirect_guest_to_login(self, app):
        guest = app.test_client()

        response = guest.get("/admin")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


class TestUserStatus:

    def test_should_deactivate_user(self, admin_client, user):
        response = admin_client.post(
            f"/admin/users/{user.id}/status",
            data={"status": "inactive"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/admin")

        db.session.refresh(user)
        assert user.is_active_account is False

    def test_should_reactivate_user(self, admin_client, user):
        user.is_active_account = False
        db.session.commit()

        response = admin_client.post(
            f"/admin/users/{user.id}/status",
            data={"status": "active"},
        )

        assert response.status_code == 302
        db.session.refresh(user)
        assert user.is_active_account is True

    def test_should_reject_self_deactivation(
        self, admin_client, admin_user
    ):
        response = admin_client.post(
            f"/admin/users/{admin_user.id}/status",
            data={"status": "inactive"},
        )

        assert response.status_code == 302
        db.session.refresh(admin_user)
        assert admin_user.is_active_account is True

        with admin_client.session_transaction() as session:
            assert (
                "error",
                "You cannot deactivate your own account.",
            ) in session.get("_flashes", [])

    def test_should_block_regular_user_status_changes(
        self, client, other_user
    ):
        response = client.post(
            f"/admin/users/{other_user.id}/status",
            data={"status": "inactive"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        db.session.refresh(other_user)
        assert other_user.is_active_account is True


class TestDeleteUser:

    def test_should_delete_regular_user(self, admin_client, user):
        user_id = user.id

        response = admin_client.post(
            f"/admin/users/{user_id}/delete"
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/admin")
        assert db.session.get(User, user_id) is None

    def test_should_reject_self_deletion(
        self, admin_client, admin_user
    ):
        admin_id = admin_user.id

        response = admin_client.post(
            f"/admin/users/{admin_id}/delete"
        )

        assert response.status_code == 302
        assert db.session.get(User, admin_id) is not None

        with admin_client.session_transaction() as session:
            assert (
                "error",
                "You cannot delete your own account.",
            ) in session.get("_flashes", [])

    def test_should_reject_deleting_another_admin(
        self, admin_client
    ):
        other_admin = User(
            username="secondadmin",
            email="secondadmin@example.com",
            role="admin",
        )
        other_admin.set_password("secret123")
        db.session.add(other_admin)
        db.session.commit()
        admin_id = other_admin.id

        response = admin_client.post(
            f"/admin/users/{admin_id}/delete"
        )

        assert response.status_code == 302
        assert db.session.get(User, admin_id) is not None

        with admin_client.session_transaction() as session:
            assert (
                "error",
                "You cannot delete another admin account.",
            ) in session.get("_flashes", [])

    def test_should_block_regular_user_deletion(
        self, client, other_user
    ):
        user_id = other_user.id

        response = client.post(
            f"/admin/users/{user_id}/delete"
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        assert db.session.get(User, user_id) is not None