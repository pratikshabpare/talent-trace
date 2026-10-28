import os, json, requests, mysql.connector
from flask import Flask, render_template, request, flash
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from docx import Document

app=Flask(__name__)
app.secret_key=os.getenv("FLASK_SECRET_KEY","local-dev-change-me")
UPLOAD=os.path.join(os.path.dirname(__file__),"uploads")
os.makedirs(UPLOAD,exist_ok=True)
app.config["MAX_CONTENT_LENGTH"]=8*1024*1024

def db():
    return mysql.connector.connect(host=os.getenv("MYSQL_HOST","localhost"),port=int(os.getenv("MYSQL_PORT","3306")),user=os.getenv("MYSQL_USER","root"),password=os.getenv("MYSQL_PASSWORD",""),database=os.getenv("MYSQL_DATABASE","resume_assessment"))
def extract(path, ext):
    if ext=="pdf": return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages).strip()
    if ext=="docx": return "\n".join(p.text for p in Document(path).paragraphs).strip()
    return open(path,encoding="utf-8",errors="ignore").read().strip()

@app.route("/")
def index(): return render_template("index.html",result=None)

@app.route("/analyze",methods=["POST"])
def analyze():
    f=request.files.get("resume"); linkedin=(request.form.get("linkedin_url") or "").strip()
    if not f or not f.filename:
        flash("Please select a resume file.","error"); return render_template("index.html",result=None),400
    filename=secure_filename(f.filename); ext=filename.rsplit(".",1)[-1].lower() if "." in filename else ""
    if ext not in {"pdf","docx","txt"}:
        flash("Upload a PDF, DOCX, or TXT file.","error"); return render_template("index.html",result=None),400
    path=os.path.join(UPLOAD,filename); f.save(path); result=None
    try:
        text=extract(path,ext)
        if len(text)<20:
            flash("Not enough text extracted. Scanned PDFs require OCR.","error"); return render_template("index.html",result=None),400
        url=os.getenv("N8N_WEBHOOK_URL","http://localhost:5678/webhook-test/resume-profile-check")
        r=requests.post(url,json={"resume_text":text,"linkedin_url":linkedin},timeout=90); r.raise_for_status(); result=r.json()
        c=result.get("candidate",{}); l=result.get("linkedin_check",{})
        conn=db()
        try:
            cur=conn.cursor()
            cur.execute("""INSERT INTO candidates(full_name,email,phone,skills_json,education_json,experience_json,linkedin_url,linkedin_format_valid,linkedin_found_in_resume,resume_filename,resume_text,parsed_result_json) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (c.get("full_name"),c.get("email"),c.get("phone"),json.dumps(c.get("skills",[])),json.dumps(c.get("education",[])),json.dumps(c.get("experience",[])),l.get("normalized_url"),bool(l.get("format_valid")),bool(l.get("url_appears_in_resume")),filename,text,json.dumps(result,ensure_ascii=False)))
            conn.commit(); result["database"]={"saved":True,"candidate_id":cur.lastrowid}; cur.close()
        finally: conn.close()
        return render_template("index.html",result=result)
    except requests.RequestException as e:
        flash("Cannot reach n8n. Start the workflow listening for a test event and check N8N_WEBHOOK_URL. "+str(e),"error")
        return render_template("index.html",result=None),502
    except mysql.connector.Error as e:
        flash("MySQL error. Check database credentials/schema. "+str(e),"error")
        return render_template("index.html",result=result),500
    except Exception as e:
        flash("Processing error: "+str(e),"error"); return render_template("index.html",result=None),500
    finally:
        if os.path.exists(path): os.remove(path)

if __name__=="__main__": app.run(host="127.0.0.1",port=5000,debug=True)
