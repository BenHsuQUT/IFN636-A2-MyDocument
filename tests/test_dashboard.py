from flask import template_rendered

class TestDashboard:

    def test_should_display_own_document(self, client, document):
        response = client.get("/dashboard")

        assert response.status_code == 200
        assert document.title.encode() in response.data
        assert document.category.encode() in response.data

    def test_should_not_display_another_users_document(
        self, client, document, other_document
    ):
        response = client.get("/dashboard")

        assert response.status_code == 200
        assert document.title.encode() in response.data
        assert other_document.title.encode() not in response.data

    def test_should_redirect_guest_to_login(self, app):
        guest = app.test_client()

        response = guest.get("/dashboard")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


class TestDocumentSearch:

    def test_should_find_matching_document(self, client, document):
        response = client.get("/dashboard", query_string={"q": "Report"})

        assert response.status_code == 200
        assert document.title.encode() in response.data

    def test_should_exclude_non_matching_document(self, client, document):
        response = client.get(
            "/dashboard", query_string={"q": "NonexistentKeyword"}
        )

        assert response.status_code == 200
        assert document.title.encode() not in response.data

    def test_should_not_find_another_users_document(
        self, app, client, document, other_document
    ):
        contexts = []

        def capture_template(sender, template, context, **extra):
            contexts.append(context)

        with template_rendered.connected_to(capture_template, app):
            response = client.get(
                "/dashboard",
                query_string={"q": other_document.title},
            )

        assert response.status_code == 200
        assert contexts

        # Check the actual search results, not the search box text
        results = contexts[-1]["docs"]
        result_ids = [doc.id for doc in results]

        assert other_document.id not in result_ids
        assert document.id not in result_ids


class TestCategoryFilter:

    def test_should_show_document_in_selected_category(
        self, app, client, document
    ):
        contexts = []

        def capture_template(sender, template, context, **extra):
            contexts.append(context)

        with template_rendered.connected_to(capture_template, app):
            response = client.get(
                "/dashboard",
                query_string={"category": "Work"},
            )

        assert response.status_code == 200
        assert contexts

        result_ids = [doc.id for doc in contexts[-1]["docs"]]
        assert document.id in result_ids

    def test_should_exclude_document_in_other_category(
        self, app, client, document
    ):
        contexts = []

        def capture_template(sender, template, context, **extra):
            contexts.append(context)

        with template_rendered.connected_to(capture_template, app):
            response = client.get(
                "/dashboard",
                query_string={"category": "Finance"},
            )

        assert response.status_code == 200
        assert contexts

        result_ids = [doc.id for doc in contexts[-1]["docs"]]
        assert document.id not in result_ids

    def test_should_exclude_another_users_document(
        self, app, client, document, other_document
    ):
        contexts = []

        def capture_template(sender, template, context, **extra):
            contexts.append(context)

        with template_rendered.connected_to(capture_template, app):
            response = client.get(
                "/dashboard",
                query_string={"category": "Work"},
            )

        assert response.status_code == 200
        assert contexts

        result_ids = [doc.id for doc in contexts[-1]["docs"]]
        assert document.id in result_ids
        assert other_document.id not in result_ids