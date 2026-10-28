
# ============================================================
# TalentTrace - Resume & LinkedIn Consistency Checker
# ============================================================
# प्रकल्पाचा उद्देश:
# 1. वापरकर्त्याकडून Resume आणि LinkedIn URL घेणे.
# 2. Resume मधून मजकूर काढणे.
# 3. Resume चा मजकूर n8n workflow कडे पाठवणे.
# 4. Gemini AI च्या मदतीने उमेदवाराची माहिती मिळवणे.
# 5. LinkedIn URL ची consistency तपासणे.
# 6. आवश्यक माहिती MySQL database मध्ये साठवणे.
# 7. Processing पूर्ण झाल्यावर uploaded file delete करणे.
# ============================================================


# -------------------- 1. आवश्यक Libraries --------------------

import os
import json
import requests
import mysql.connector

from flask import Flask, render_template, request, flash
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from docx import Document


# -------------------- 2. Flask Application --------------------

# Flask application तयार करणे.
# याच application मधून browser requests हाताळल्या जातात.
app = Flask(__name__)

# Flask session आणि flash messages साठी secret key.
# Production मध्ये ही key environment variable मधून द्यावी.
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "local-dev-change-me"
)


# -------------------- 3. File Upload Configuration --------------------

# app.py ज्या folder मध्ये आहे, त्याच ठिकाणी uploads folder तयार होईल.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

# uploads folder अस्तित्वात नसेल तर तयार करणे.
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# एका upload चा कमाल आकार 8 MB ठेवणे.
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

# फक्त या file extensions स्वीकारायच्या आहेत.
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


# -------------------- 4. MySQL Connection Function --------------------

def db():
    """
    MySQL database शी connection तयार करते.

    Database credentials environment variables मधून घेतले जातात.
    त्यामुळे password थेट source code मध्ये लिहावा लागत नाही.
    """

    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "resume_assessment")
    )


# -------------------- 5. Resume मधून Text काढणे --------------------

def extract_text(file_path, extension):
    """
    PDF, DOCX किंवा TXT file मधून वाचता येणारा मजकूर काढते.

    PDF  : प्रत्येक page मधील text काढते.
    DOCX : paragraph मधील text काढते.
    TXT  : file मधील मजकूर वाचते.

    टीप:
    Scanned PDF मध्ये मजकूर image स्वरूपात असल्यास OCR लागू शकते.
    """

    if extension == "pdf":
        pdf = PdfReader(file_path)

        # प्रत्येक page मधील text काढून एकत्र करणे.
        pages = [
            page.extract_text() or ""
            for page in pdf.pages
        ]

        return "\n".join(pages).strip()

    elif extension == "docx":
        document = Document(file_path)

        # Word document मधील सर्व paragraphs एकत्र करणे.
        paragraphs = [
            paragraph.text
            for paragraph in document.paragraphs
        ]

        return "\n".join(paragraphs).strip()

    elif extension == "txt":
        # UTF-8 encoding वापरून text file वाचणे.
        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as file:
            return file.read().strip()

    else:
        # Unsupported extension असल्यास error देणे.
        raise ValueError("Unsupported resume file format.")


# -------------------- 6. Home Page --------------------

@app.route("/")
def index():
    """
    Browser मध्ये मुख्य form दाखवते.
    सुरुवातीला कोणताही analysis result नसतो.
    """

    return render_template(
        "index.html",
        result=None
    )


# -------------------- 7. Resume Analysis Route --------------------

@app.route("/analyze", methods=["POST"])
def analyze():
    """
    हा application चा मुख्य workflow आहे.

    Browser मधून आलेली माहिती:
    - Resume file
    - LinkedIn profile URL

    पुढे:
    - File validation
    - Text extraction
    - n8n API request
    - Response processing
    - MySQL insertion
    - Result display
    - Temporary file deletion
    """

    # Form मधून uploaded resume घेणे.
    uploaded_file = request.files.get("resume")

    # Form मधून LinkedIn URL घेऊन बाहेरील spaces काढणे.
    linkedin_url = (
        request.form.get("linkedin_url") or ""
    ).strip()

    # -------------------- 7.1 File Validation --------------------

    # वापरकर्त्याने file निवडली आहे का ते तपासणे.
    if not uploaded_file or not uploaded_file.filename:
        flash("Please select a resume file.", "error")

        return render_template(
            "index.html",
            result=None
        ), 400

    # File name सुरक्षित करणे.
    # यामुळे filename मधील path traversal सारखे धोके कमी होतात.
    filename = secure_filename(uploaded_file.filename)

    # File extension काढणे.
    extension = (
        filename.rsplit(".", 1)[-1].lower()
        if "." in filename
        else ""
    )

    # फक्त PDF, DOCX आणि TXT स्वीकारणे.
    if extension not in ALLOWED_EXTENSIONS:
        flash(
            "Upload a PDF, DOCX, or TXT file.",
            "error"
        )

        return render_template(
            "index.html",
            result=None
        ), 400

    # प्रत्येक upload साठी वेगळे temporary filename वापरणे.
    # त्यामुळे एकाच नावाच्या files एकमेकींवर overwrite होणार नाहीत.
    import uuid

    temporary_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = os.path.join(
        UPLOAD_FOLDER,
        temporary_name
    )

    # पुढे analysis result येथे ठेवला जाईल.
    result = None

    try:
        # -------------------- 7.2 File Save आणि Text Extraction --------------------

        # Uploaded file तात्पुरती save करणे.
        uploaded_file.save(file_path)

        # Resume मधून मजकूर काढणे.
        resume_text = extract_text(
            file_path,
            extension
        )

        # मजकूर पुरेसा नसेल तर processing थांबवणे.
        if len(resume_text) < 20:
            flash(
                "Not enough text extracted. "
                "Scanned PDFs may require OCR.",
                "error"
            )

            return render_template(
                "index.html",
                result=None
            ), 400

        # -------------------- 7.3 n8n Webhook ला Request --------------------

        # Production webhook URL environment variable मधून घेतली जाते.
        # उदाहरण:
        # http://localhost:5678/webhook/resume-profile-check
        #
        # Test mode वापरत असल्यास N8N_WEBHOOK_URL मध्ये
        # /webhook-test/ असलेली URL द्यावी लागेल.

        webhook_url = os.getenv(
            "N8N_WEBHOOK_URL",
            "http://localhost:5678/webhook/resume-profile-check"
        )

        # Resume text आणि LinkedIn URL n8n कडे पाठवणे.
        # n8n पुढे Gemini API वापरून माहिती extract करते.
        response = requests.post(
            webhook_url,
            json={
                "resume_text": resume_text,
                "linkedin_url": linkedin_url
            },
            timeout=90
        )

        # HTTP error असल्यास exception निर्माण होईल.
        response.raise_for_status()

        # n8n कडून आलेला JSON response Python dictionary मध्ये बदलणे.
        result = response.json()

        # AI response यशस्वी आहे का ते तपासणे.
        if not isinstance(result, dict) or not result.get("success"):
            raise ValueError(
                "The resume parsing workflow returned an unsuccessful result."
            )

        # Candidate details आणि LinkedIn check वेगळे काढणे.
        candidate = result.get("candidate") or {}
        linkedin_check = result.get("linkedin_check") or {}

        # आवश्यक माहिती योग्य स्वरूपात आहे का ते तपासणे.
        if not isinstance(candidate, dict):
            raise ValueError(
                "Invalid candidate data returned by n8n."
            )

        if not isinstance(linkedin_check, dict):
            raise ValueError(
                "Invalid LinkedIn check returned by n8n."
            )

        # -------------------- 7.4 MySQL Connection --------------------

        # MySQL database शी connection तयार करणे.
        connection = db()

        try:
            # SQL query चालवण्यासाठी cursor तयार करणे.
            cursor = connection.cursor()

            # -------------------- 7.5 Candidate Data Insert --------------------

            # फक्त आवश्यक माहिती save केली जाते.
            #
            # मुद्दाम वगळलेले columns:
            # resume_text        -> संपूर्ण resume text साठवला जात नाही.
            # parsed_result_json -> पूर्ण AI response साठवला जात नाही.
            #
            # Skills, education आणि experience JSON स्वरूपात साठवले जातात.
            # त्यामुळे lists आणि structured project details टिकून राहतात.

            insert_query = """
                INSERT INTO candidates (
                    full_name,
                    email,
                    phone,
                    skills_json,
                    education_json,
                    experience_json,
                    linkedin_url,
                    linkedin_format_valid,
                    linkedin_found_in_resume,
                    resume_filename
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            # SQL query साठी values स्वतंत्रपणे देणे.
            # यामुळे values query मध्ये थेट जोडण्याची गरज राहत नाही.
            values = (
                candidate.get("full_name"),
                candidate.get("email"),
                candidate.get("phone"),

                json.dumps(
                    candidate.get("skills", []),
                    ensure_ascii=False
                ),

                json.dumps(
                    candidate.get("education", []),
                    ensure_ascii=False
                ),

                json.dumps(
                    candidate.get("experience", []),
                    ensure_ascii=False
                ),

                # Submitted URL जतन करणे.
                # त्यामुळे recruiter ने दिलेला URL तपासता येतो.
                linkedin_url or None,

                # URL format valid आहे का?
                # Missing value असल्यास NULL ठेवणे.
                (
                    bool(linkedin_check["format_valid"])
                    if linkedin_check.get("format_valid") is not None
                    else None
                ),

                # Submitted URL resume मध्ये सापडला का?
                # Missing value असल्यास NULL ठेवणे.
                (
                    bool(linkedin_check["url_appears_in_resume"])
                    if linkedin_check.get("url_appears_in_resume") is not None
                    else None
                ),

                # मूळ filename ठेवणे; temporary UUID filename नाही.
                filename
            )

            # SQL query execute करणे.
            cursor.execute(
                insert_query,
                values
            )

            # Database transaction commit केल्यावर record save होतो.
            connection.commit()

            # Insert झालेल्या record चा ID मिळवणे.
            candidate_id = cursor.lastrowid

            # Frontend ला database save status देणे.
            result["database"] = {
                "saved": True,
                "candidate_id": candidate_id
            }

        except Exception:
            # Insert किंवा commit अयशस्वी झाल्यास बदल rollback करणे.
            connection.rollback()

            # Error पुढील error handler कडे पाठवणे.
            raise

        finally:
            # Cursor आणि database connection बंद करणे.
            if "cursor" in locals():
                cursor.close()

            connection.close()

        # -------------------- 7.6 Result Browser मध्ये दाखवणे --------------------

        # Parsing आणि database save यशस्वी झाल्यावर result page दाखवणे.
        return render_template(
            "index.html",
            result=result
        )

    # -------------------- 8. Error Handling --------------------

    except requests.RequestException:
        # n8n workflow पर्यंत पोहोचता आले नाही किंवा HTTP error आला.
        app.logger.exception("n8n webhook request failed")

        flash(
            "Cannot reach n8n. Check whether the workflow is active "
            "and verify N8N_WEBHOOK_URL.",
            "error"
        )

        return render_template(
            "index.html",
            result=None
        ), 502

    except mysql.connector.Error:
        # MySQL connection किंवा query अयशस्वी झाल्यास.
        app.logger.exception("MySQL database operation failed")

        # Parsing झाले असले तरी database save झाले नसेल.
        # त्यामुळे result page वर स्पष्ट status दाखवणे.
        if isinstance(result, dict):
            result["database"] = {
                "saved": False,
                "candidate_id": None
            }

            flash(
                "Resume parsed, but the candidate could not be saved "
                "to MySQL. Check the server log.",
                "error"
            )

            return render_template(
                "index.html",
                result=result
            ), 500

        flash(
            "A database error occurred. Check the server log.",
            "error"
        )

        return render_template(
            "index.html",
            result=None
        ), 500

    except (ValueError, json.JSONDecodeError):
        # Text extraction किंवा response format मध्ये समस्या असल्यास.
        app.logger.exception("Resume processing or response validation failed")

        flash(
            "The resume could not be processed. "
            "Check the file and workflow response.",
            "error"
        )

        return render_template(
            "index.html",
            result=None
        ), 500

    except Exception:
        # इतर अनपेक्षित errors log करणे.
        app.logger.exception("Unexpected application error")

        flash(
            "An unexpected error occurred. Please try again.",
            "error"
        )

        return render_template(
            "index.html",
            result=None
        ), 500

    finally:
        # -------------------- 9. Temporary File Cleanup --------------------

        # Processing यशस्वी झाले किंवा error आला तरी
        # तात्पुरती uploaded file delete करण्याचा प्रयत्न करणे.
        #
        # हा cleanup फक्त या application च्या uploads folder मधील
        # temporary file साठी आहे.
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                app.logger.exception(
                    "Could not delete temporary uploaded file"
                )


# -------------------- 10. Application Start --------------------

if __name__ == "__main__":
    # Flask development server सुरू करणे.
    # Browser मध्ये http://127.0.0.1:5000 उघडा.
    #
    # debug=True हे फक्त local development साठी वापरा.
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
