from project.models import db, Category


class TestAddCategory:

    def test_should_add_category(self, client, user):
        response = client.post(
            "/categories/add", data={"name": "School"}
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

        category = Category.query.filter_by(
            user_id=user.id, name="School"
        ).first()

        assert category is not None

    def test_should_reject_empty_category_name(self, client):
        count_before = Category.query.count()

        response = client.post(
            "/categories/add", data={"name": "   "}
        )

        assert response.status_code == 302
        assert Category.query.count() == count_before

        with client.session_transaction() as session:
            messages = session.get("_flashes", [])
            assert ("error", "Category name can't be empty.") in messages

    def test_should_reject_reserved_category_name(self, client):
        count_before = Category.query.count()

        response = client.post(
            "/categories/add", data={"name": "Uncategorized"}
        )

        assert response.status_code == 302
        assert Category.query.count() == count_before

        with client.session_transaction() as session:
            messages = session.get("_flashes", [])
            assert ("error", "That name is reserved.") in messages

    def test_should_reject_duplicate_category_name(self, client, user):
        db.session.add(Category(user_id=user.id, name="School"))
        db.session.commit()
        count_before = Category.query.count()

        response = client.post(
            "/categories/add", data={"name": "School"}
        )

        assert response.status_code == 302
        assert Category.query.count() == count_before

        with client.session_transaction() as session:
            messages = session.get("_flashes", [])
            assert (
                "error",
                'You already have a category named "School".',
            ) in messages


class TestRenameCategory:

    def test_should_rename_category_and_update_documents(
        self, client, user, document
    ):
        category = Category(user_id=user.id, name="Work")
        db.session.add(category)
        db.session.commit()

        response = client.post(
            f"/categories/{category.id}/rename",
            data={"name": "School"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

        db.session.refresh(category)
        db.session.refresh(document)

        assert category.name == "School"
        assert document.category == "School"

    def test_should_reject_empty_name(self, client, user):
        category = Category(user_id=user.id, name="Work")
        db.session.add(category)
        db.session.commit()

        response = client.post(
            f"/categories/{category.id}/rename",
            data={"name": "   "},
        )

        assert response.status_code == 302
        db.session.refresh(category)
        assert category.name == "Work"

        with client.session_transaction() as session:
            assert (
                "error", "Category name can't be empty."
            ) in session.get("_flashes", [])

    def test_should_reject_duplicate_name(self, client, user):
        category = Category(user_id=user.id, name="Work")
        db.session.add(category)
        db.session.add(Category(user_id=user.id, name="School"))
        db.session.commit()

        response = client.post(
            f"/categories/{category.id}/rename",
            data={"name": "School"},
        )

        assert response.status_code == 302
        db.session.refresh(category)
        assert category.name == "Work"

        with client.session_transaction() as session:
            assert (
                "error",
                'You already have a category named "School".',
            ) in session.get("_flashes", [])

    def test_should_reject_another_users_category(
        self, client, other_user
    ):
        category = Category(user_id=other_user.id, name="Private")
        db.session.add(category)
        db.session.commit()

        response = client.post(
            f"/categories/{category.id}/rename",
            data={"name": "Changed"},
        )

        assert response.status_code == 403
        db.session.refresh(category)
        assert category.name == "Private"

    def test_should_return_404_for_missing_category(self, client):
        response = client.post(
            "/categories/9999/rename",
            data={"name": "School"},
        )

        assert response.status_code == 404


class TestDeleteCategory:

    def test_should_delete_category_and_uncategorize_documents(
        self, client, user, document
    ):
        category = Category(user_id=user.id, name="Work")
        db.session.add(category)
        db.session.commit()
        category_id = category.id

        response = client.post(
            f"/categories/{category_id}/delete"
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        assert db.session.get(Category, category_id) is None

        db.session.refresh(document)
        assert document.category == "Uncategorized"

    def test_should_reject_another_users_category(
        self, client, other_user
    ):
        category = Category(user_id=other_user.id, name="Private")
        db.session.add(category)
        db.session.commit()
        category_id = category.id

        response = client.post(
            f"/categories/{category_id}/delete"
        )

        assert response.status_code == 403
        assert db.session.get(Category, category_id) is not None

    def test_should_return_404_for_missing_category(self, client):
        response = client.post("/categories/9999/delete")

        assert response.status_code == 404

    def test_should_redirect_guest_to_login(self, app, user):
        category = Category(user_id=user.id, name="Work")
        db.session.add(category)
        db.session.commit()
        category_id = category.id
        guest = app.test_client()

        response = guest.post(
            f"/categories/{category_id}/delete"
        )

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]
        assert db.session.get(Category, category_id) is not None