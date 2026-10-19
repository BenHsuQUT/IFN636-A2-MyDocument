# IFN636-A2-MyDocument (PersonalDocumentManager)-Ben-Hsu/ Autumn Mai/ Hsin-Ting Tu/ Sophie Jeng

A Flask + Jinja2 + MySQL project: a personal document manager UI, using HTML/ CSS and Bootstrap. This build is a scoped-down demo — see **Known Limitations** for exactly which features are real and non-functional.

## Setup

1. **Create the MySQL database**

   ```sql
   CREATE DATABASE personal_document_manager CHARACTER SET utf8mb4;
   ```

2. **Configure environment variables**

   ```bash
   # edit .env with your MySQL credentials
   ```

3. **Install dependencies** (a virtual environment is recommended)

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```


4. **Run the server** — from the project root:

   ```bash
   python run.py
   ```

   Open http://127.0.0.1:5000 

## Architecture Summary

```
IFN636-A1-PersonalDocumentManager-Ben-Hsu/
├── run.py               # entry point — launches the app from the project root
└── project/             # a proper Python package (has __init__.py)
   ├── __init__.py
   ├── app.py            # all routes: auth, user dashboard, upload, admin dashboard
   ├── config.py         # configuration (MySQL connection, upload limits, storage quotas)
   ├── models.py         # User and Document SQLAlchemy models
   ├── utils.py          # login_required / admin_required decorators, Jinja filters
   ├── seed.py           # one-off demo data script
   ├── templates/        # server-rendered Jinja2 pages
   └── static/
       └──css/style.css  # styling design
       └──js/app.js      #slight js codes from w3schools for supporting drag&drop functions and dropdowns
```

## Known Limitations

This build keeps only a few flows fully working end-to-end; everything else is UI-only so the screens can be demoed without a deeper backend.

**Working Functions (version 1.0)**
- Sign up, sign in, sign out
- Core document CRUD functions — save title, category, description, file size as metadata in the database and save file in the project folder, deletes document, update document title, and download document. Only `.pdf`, `.docx`, and `.txt` are accepted; other file types are rejected.
- Core Category CRUD functions  — create category, changing a document's category from the dashboard row dropdown (picking one of your existing categories), update category title, and delete a category
- Opening the "My Category" panel to view your categories
- Opening the "upload document" panel to upload your documents
- Toggling a user's Active/Inactive status on the admin dashboard

**Non-functional (present for the UI, no backend effect) (expected to be developed in version 2.0):**
- Search, and the Type / Category / Date / Size / Sort filters on the dashboard, and the search/role/status filters on the admin dashboard — these are decorative; the lists always show everything
- Restore on an older version
- "Continue with Google / Apple" buttons, the admin sidebar's "Settings" link, and "Forgot password?"
- preview document

**Further expectation:**
- Allowing a file to have multiple categories (must redesign the database and both the backend and frontend, but allow more flexible organisation for users)

**Other notes:**
- Storage quotas (20 GB/user, 500 GB total) are hardcoded demo numbers in `config.py`
- Sessions don't expire; replace `SECRET_KEY` with a random value before deploying anywhere real
- Categories are free-text fields on each document, not a separate managed table
- Allowed upload extensions (`ALLOWED_EXTENSIONS` in `config.py`) are currently just `pdf`, `docx`, `txt`

## Deployment URL

The deployment url cannot be provided, as the public address cannot be consistent because the EC2 instance will be shot down every midnight. Please request the project owner for the testing public address.
