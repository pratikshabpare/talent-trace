# Resume & LinkedIn Consistency Checker

Flow: browser form -> Flask file upload -> PDF/DOCX/TXT text extraction -> existing n8n webhook/Gemini -> MySQL save -> results page.

## Setup
1. Create schema: `mysql -u root -p < schema.sql`
2. Create virtualenv and install dependencies:
   `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
3. Set environment variables in this same terminal:
   `export MYSQL_HOST=localhost MYSQL_PORT=3306 MYSQL_USER=root MYSQL_PASSWORD='YOUR_MYSQL_PASSWORD' MYSQL_DATABASE=resume_assessment`
   `export N8N_WEBHOOK_URL='http://localhost:5678/webhook-test/resume-profile-check'`
   `export FLASK_SECRET_KEY='replace-this-secret'`
4. In n8n, open the existing workflow and click **Listen for test event**.
5. Run `python app.py` and open `http://127.0.0.1:5000`.
6. For a published workflow, use `http://localhost:5678/webhook/resume-profile-check` as N8N_WEBHOOK_URL.

## Notes
Test webhook is one-shot; click Listen for test event before each test. Text-based PDFs are supported; scanned PDFs require OCR. LinkedIn check is format/consistency only, not profile scraping or identity verification. This is a local assessment prototype; add authentication, CSRF protection, rate limiting, and a retention policy before public deployment. The uploaded file is deleted after processing, but extracted text is stored in MySQL. Never commit API keys into workflow JSON.
# talent-trace
# profilesync-ai
# profilesync-ai
