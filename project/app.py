from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for,session, flash, send_from_directory, abort, jsonify

from project.config import Config
from project.models import db
from project.utils import login_required, admin_required, register_template_filters
from project.facades import MyDocumentFacade, ValidationError, AccessDeniedError

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
register_template_filters(app)

facade = MyDocumentFacade(app.config)
# -------------------------------------------------------------------- getter --
def get_current_user():
    return facade.get_user(session.get("user_id"))


def flash_errors(error):
    for message in error.messages:
        flash(message, "error")


@app.context_processor
def inject_current_user():
    return {"current_user": get_current_user()}

# -------------------------------------------------------------------- auth --
@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        try:
            facade.register_user(username, email, password)
        except ValidationError as e:
            flash_errors(e)
            return render_template("register.html", username=username, email=email)

        flash("Account created successfully, please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", username="", email="")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("admin_dashboard" if session.get("role") == "admin" else "dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            user = facade.authenticate(username, password)
        except ValidationError as e:
            flash_errors(e)
        else:
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role

            flash(f"Welcome back, {user.username}!", "success")
            next_url = request.args.get("next")
            if user.is_admin:
                return redirect(url_for("admin_dashboard"))
            return redirect(next_url or url_for("dashboard"))

    return render_template("login.html", username="")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))

# -------------------------------------------------------------------- user_dashboard --
@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("admin_dashboard" if session.get("role") == "admin" else "dashboard"))
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    search_query = request.args.get("q", "").strip()
    file_type = request.args.get("type", "").strip()
    category_filter = request.args.get("category", "").strip()
    date_filter = request.args.get("date", "").strip()
    size_filter = request.args.get("size", "").strip()

    data = facade.get_user_dashboard_data(
        get_current_user(),
        search_query=search_query,
        category_filter=category_filter,
        file_type=file_type,
        date_filter=date_filter,
        size_filter=size_filter
    )
    
    return render_template("user_dashboard.html", **data, today=datetime.utcnow())

# -----------------------category--------------------------------
@app.route("/categories/add", methods=["POST"])
@login_required
def add_category():
    try:
        name = facade.add_category(get_current_user(), request.form.get("name", ""))
        flash(f'Category "{name}" added.', "success")
    except ValidationError as e:
        flash_errors(e)
    return redirect(url_for("dashboard"))


@app.route("/categories/<int:category_id>/rename", methods=["POST"])
@login_required
def rename_category(category_id):
    try:
        old_name, new_name = facade.rename_category(
            get_current_user(), category_id, request.form.get("name", "")
        )
        flash(f'Renamed "{old_name}" to "{new_name}".', "success")
    except ValidationError as e:
        flash_errors(e)
    except AccessDeniedError:
        abort(403)
    return redirect(url_for("dashboard"))


@app.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
def delete_category(category_id):
    try:
        old_name = facade.delete_category(get_current_user(), category_id)
    except AccessDeniedError:
        abort(403)
    flash(f'Deleted category "{old_name}".', "success")
    return redirect(url_for("dashboard"))

# -----------------------document crud--------------------------------
@app.route("/upload", methods=["POST"])
@login_required
def upload_document():
    try:
        facade.upload_document(
            get_current_user(),
            request.files.get("file"),
            title=request.form.get("title", ""),
            category=request.form.get("category", ""),
            notes=request.form.get("notes", ""),
        )
        flash("Upload successful.", "success")
    except ValidationError as e:
        flash_errors(e)
    except AccessDeniedError:
        abort(403)
    return redirect(url_for("dashboard"))

# -----------------------document_details-----------------------
@app.route("/documents/<int:doc_id>")
@login_required
def document_details(doc_id):
    try:
        doc = facade.get_document_for(get_current_user(), doc_id)
    except AccessDeniedError:
        abort(403)
    return render_template("document_details.html", doc=doc, versions=facade.get_all_versions(doc))


@app.route("/api/documents/<int:doc_id>/versions")
@login_required
def api_version_history(doc_id):
    try:
        doc = facade.get_document_for(get_current_user(), doc_id)
    except AccessDeniedError:
        abort(403)
    return jsonify({
        "document_id": doc.id,
        "title": doc.title,
        "current_version": doc.version,
        "versions": [
            {**m.to_dict(), "is_current": m.version == doc.version}
            for m in facade.get_all_versions(doc)
        ],
    })


@app.route("/documents/<int:doc_id>/versions/upload", methods=["POST"])
@login_required
def upload_new_version(doc_id):
    try:
        doc = facade.upload_new_version(get_current_user(), doc_id, request.files.get("file"))
        flash(f"Uploaded V.{doc.version} of \"{doc.title}\".", "success")
    except ValidationError as e:
        flash_errors(e)
    except AccessDeniedError:
        abort(403)
    return redirect(url_for("document_details", doc_id=doc_id))


@app.route("/documents/<int:doc_id>/versions/<int:version>/restore", methods=["POST"])
@login_required
def restore_version(doc_id, version):
    try:
        doc = facade.restore_version(get_current_user(), doc_id, version)
        flash(f"Restored V.{version} as V.{doc.version} of \"{doc.title}\".", "success")
    except ValidationError as e:
        flash_errors(e)
    except AccessDeniedError:
        abort(403)
    return redirect(url_for("document_details", doc_id=doc_id))


@app.route("/documents/<int:doc_id>/update", methods=["POST"])
@login_required
def update_document(doc_id):
    try:
        doc = facade.update_document(
            get_current_user(), doc_id,
            title=request.form.get("title"),
            category=request.form.get("category"),
            notes=request.form.get("notes", ""),
        )
    except AccessDeniedError:
        abort(403)
    flash("Document details updated.", "success")

    next_url = request.form.get("next", "")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("document_details", doc_id=doc.id))

#check
@app.route("/documents/<int:doc_id>/download")
@login_required
def download_document(doc_id):
    try:
        directory, stored_filename, download_name = facade.get_download_info(get_current_user(), doc_id)
    except AccessDeniedError:
        abort(403)
    return send_from_directory(directory, stored_filename, as_attachment=True, download_name=download_name)

@app.route("/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
def delete_document(doc_id):
    user = get_current_user()
    try:
        owner_id = facade.delete_document(user, doc_id)
    except AccessDeniedError:
        abort(403)

    flash("Document deleted.", "success")
    if user.is_admin and owner_id != user.id:
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("dashboard"))

# ------------------------------------------------------------ admin pages --
@app.route("/admin")
@admin_required
def admin_dashboard():
    data = facade.get_admin_dashboard_data()
    return render_template("admin_dashboard.html", **data, today=datetime.utcnow())


@app.route("/admin/users/<int:user_id>/status", methods=["POST"])
@admin_required
def update_user_status(user_id):
    try:
        user = facade.set_user_status(session.get("user_id"), user_id, request.form.get("status", "active"))
        flash(f"Updated {user.username}'s status.", "success")
    except ValidationError as e:
        flash_errors(e)
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    try:
        username = facade.delete_user(session.get("user_id"), user_id)
        flash(f"Deleted user {username}.", "success")
    except ValidationError as e:
        flash_errors(e)
    return redirect(url_for("admin_dashboard"))


#-------------------------------------------------error handlers--
@app.errorhandler(404)
def not_found(e):
    return render_template(
        "error.html",
        error_title="Not Found",
        error_message="Sorry, but we cannot find what you are looking for.",
    ), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template(
        "error.html",
        error_title="Server Error",
        error_message="Sorry, but the server has encountered an error. Please try again in a few minutes.",
    ), 500

# --------------------------------------------------------------- CLI/setup --
@app.cli.command("init-db") #flask --app pdm_project.app init-db
def init_db():
    db.create_all()
    print("Database tables created.")


@app.cli.command("create-admin") #flask --app pdm_project.app create-admin
def create_admin():
    
    import getpass
    username = input("Admin username: ").strip()
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Admin password: ")

    try:
        facade.create_admin(username, email, password)
    except ValidationError as e:
        for message in e.messages:
            print(message)
        return
    print(f"Admin {username} created.")
