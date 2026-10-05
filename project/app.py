import os
import shutil
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for,session, flash, send_from_directory, abort

from project.config import Config
from project.models import db, User, Document
from project.utils import login_required, admin_required, register_template_filters
from project.facades import DocumentManagerFacade, ValidationError, AccessDeniedError

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
register_template_filters(app)

facade = DocumentManagerFacade(app.config)
# -------------------------------------------------------------------- getter --
def get_current_user():
    uid = session.get("user_id")
    return User.query.get(uid) if uid else None


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

        errors = []
        if not username or not email or not password:
            errors.append("Please fill in all fields.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if User.query.filter_by(username=username).first():
            errors.append("This username is already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("This email is already registered.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", username=username, email=email)

        user = User(username=username, email=email, role="user")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

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
        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash("Incorrect username or password.", "error")
        elif not user.is_active_account:
            flash("This account has been deactivated. Please contact an administrator.", "error")
        else:
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            user.last_login_at = datetime.utcnow()
            db.session.commit()

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
    data = facade.get_user_dashboard_data(get_current_user())
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
            version_of=request.form.get("version_of", ""),
            title=request.form.get("title", ""),
            category=request.form.get("category", ""),
            notes=request.form.get("notes", ""),
        )
        flash("Upload successful.", "success")
    except ValidationError as e:
        flash_errors(e)
    return redirect(url_for("dashboard"))

# -----------------------document_details-----------------------
@app.route("/documents/<int:doc_id>")
@login_required
def document_details(doc_id):
    try:
        doc = facade.get_document_for(get_current_user(), doc_id)
    except AccessDeniedError:
        abort(403)
    return render_template("document_details.html", doc=doc, versions=doc.versions())


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
    all_users = User.query.order_by(User.created_at.asc()).all()
    total_users = len(all_users)
    active_users = sum(1 for u in all_users if u.is_active_account)
    inactive_users = total_users - active_users
    new_this_week = sum(
        1 for u in all_users
        if u.created_at and u.created_at >= datetime.utcnow() - timedelta(days=7)
    )

    total_documents = Document.query.filter_by(is_latest=True).count()
    total_storage = sum(u.total_storage_bytes() for u in all_users)
    quota = app.config["ADMIN_TOTAL_QUOTA_BYTES"]
    percent_used = round((total_storage / quota) * 100, 1) if quota else 0

    return render_template(
        "admin_dashboard.html",
        users=all_users,
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        new_this_week=new_this_week,
        total_documents=total_documents,
        total_storage=total_storage,
        percent_used=min(percent_used, 100),
        quota=quota,
        today=datetime.utcnow()
    )


@app.route("/admin/users/<int:user_id>/status", methods=["POST"])
@admin_required
def update_user_status(user_id):
    user = User.query.get_or_404(user_id)
    new_status = request.form.get("status", "active")

    if user.id == session.get("user_id") and new_status != "active":
        flash("You cannot deactivate your own account.", "error")
        return redirect(url_for("admin_dashboard"))

    user.is_active_account = (new_status == "active")
    db.session.commit()
    flash(f"Updated {user.username}'s status.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == session.get("user_id"):
        flash("You cannot delete your own account.", "error")
        return redirect(url_for("admin_dashboard"))

    folder = os.path.join(app.config["UPLOAD_FOLDER"], str(user.id))
    if os.path.isdir(folder):
        shutil.rmtree(folder)

    db.session.delete(user)
    db.session.commit()
    flash(f"Deleted user {user.username}.", "success")
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

    if User.query.filter_by(username=username).first():
        print("This username already exists.")
        return

    admin = User(username=username, email=email, role="admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"Admin {username} created.")
