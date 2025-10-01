import os
import json
import uuid
import re
import requests
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from pypdf import PdfReader
import google.generativeai as genai
import mysql.connector
import config  # your config.py with api_key

# ----------------------------
# Configure Gemini
# ----------------------------
genai.configure(api_key=config.api_key)

# ----------------------------
# Flask app
# ----------------------------
app = Flask(__name__)
CORS(app)

# ----------------------------
# Upload folder
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------------------
# MySQL connection helper
# ----------------------------
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "Abhishek@21",
    "database": "FRA_Claims"
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ----------------------------
# PDF -> English using Gemini
# ----------------------------
def translate_pdf_to_english(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text += page_text + "\n"

    if not text.strip():
        return ""

    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"Translate the following text into English:\n\n{text}"
    response = model.generate_content(prompt)
    return response.text or ""

# ----------------------------
# Geolocation helper
# ----------------------------
def get_location(village, tehsil, district):
    if not village or not tehsil or not district:
        return {"lat": None, "lon": None}
    query = f"{village}, {tehsil}, {district}, India"
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, params={"q": query, "format": "json"}, headers=headers, timeout=10)
        results = r.json()
        if results:
            return {"lat": float(results[0]["lat"]), "lon": float(results[0]["lon"])}
    except Exception as e:
        print("Geocode error:", e)
    return {"lat": None, "lon": None}

# ----------------------------
# Insert claim into DB
# ----------------------------
def insert_claim_to_db(claim):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure community exists
        cursor.execute("SELECT Community_ID FROM communities WHERE Community_Name = %s", (claim.get("Community_Name"),))
        result = cursor.fetchone()

        if result:
            community_id = result[0]
        else:
            cursor.execute("""
                INSERT INTO communities (Community_Name, latitude, longitude)
                VALUES (%s, %s, %s)
            """, (
                claim.get("Community_Name"),
                claim["Location"].get("lat") or 0.0,
                claim["Location"].get("lon") or 0.0
            ))
            conn.commit()
            community_id = cursor.lastrowid

        # Insert into users
        query = """
        INSERT INTO users (
            DOC_ID_NUMBER, Community_Name, Community_ID, Claim_Person,
            Gender, Occupation, document_status, village_name,
            tehsil_name, district_name, latitude, longitude
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            claim.get("DOC_ID_NUMBER"),
            claim.get("Community_Name"),
            community_id,
            claim.get("Claim_Person"),
            claim.get("Gender"),
            claim.get("Occupation"),
            claim.get("document_status"),
            claim.get("village_name"),
            claim.get("tehsil_name"),
            claim.get("district_name"),
            claim["Location"].get("lat"),
            claim["Location"].get("lon")
        )
        cursor.execute(query, values)

        # Update community counters
        status = claim.get("document_status")
        if status in ["in_process", "approved", "rejected", "delayed"]:
            update_query = f"""
            UPDATE communities
            SET total_claims = total_claims + 1,
                total_{status} = total_{status} + 1
            WHERE Community_ID = %s
            """
            cursor.execute(update_query, (community_id,))
        else:
            cursor.execute("""
                UPDATE communities
                SET total_claims = total_claims + 1
                WHERE Community_ID = %s
            """, (community_id,))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print("DB insert error:", e)
        return False

# ----------------------------
# Routes: Dashboard, Search, Upload
# ----------------------------
@app.route('/')
def index():
    return render_template("dashboard.html")

@app.route('/search')
def search():
    return render_template("search.html")

@app.route('/upload', methods=['GET', 'POST'])
def upload_page():
    if request.method == 'POST':
        if "file" not in request.files:
            return jsonify({"success": False, "message": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "message": "No selected file"}), 400

        save_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(save_path)

        translated_text = translate_pdf_to_english(save_path)
        if not translated_text.strip():
            return jsonify({"success": False, "message": "No extractable text found in PDF."}), 400

        prompt = f"""
        Extract the following info and return a single JSON dictionary:

        {{
          "Community_Name":"<community>",
          "Community_ID":"<id or null>",
          "Gender":"<Male/Female/Other>",
          "village_name":"<village>",
          "tehsil_name":"<tehsil>",
          "district_name":"<district>",
          "Claim_Person":"<name>",
          "Occupation":"<occupation>",
          "document_status":"<in_process/approved/rejected/delayed>"
        }}

        Text: {translated_text}
        """
        resp = genai.GenerativeModel("gemini-2.5-flash").generate_content(prompt)
        raw_output = resp.text or ""
        clean_output = re.sub(r"```(?:json)?", "", raw_output).strip()

        try:
            claim = json.loads(clean_output)
        except Exception as e:
            print("JSON parse error:", e)
            claim = {"raw_output": clean_output}

        claim["DOC_ID_NUMBER"] = int(str(uuid.uuid4().int)[:8])
        claim["Location"] = get_location(
            claim.get("village_name"),
            claim.get("tehsil_name"),
            claim.get("district_name")
        )

        out_name = f"{claim['DOC_ID_NUMBER']}.json"
        out_path = os.path.join(UPLOAD_FOLDER, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(claim, f, ensure_ascii=False, indent=2)

        db_status = insert_claim_to_db(claim)

        return jsonify({
            "success": True,
            "message": f"Processed and saved as {out_name} (DB insert: {'ok' if db_status else 'failed'})",
            "data": claim
        })

    else:
        return render_template("upload.html")

# ----------------------------
# API: Map Data
# ----------------------------
@app.route("/map-data", methods=["GET"])
def map_data_route():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                u.Claim_Person, u.village_name, u.tehsil_name, u.district_name,
                u.latitude, u.longitude, u.Community_ID, u.document_status
            FROM users u 
            WHERE u.latitude IS NOT NULL AND u.longitude IS NOT NULL
        """)
        rows = cursor.fetchall()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# ----------------------------
# API: Summary
# ----------------------------
@app.route('/api/summary')
def summary():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM communities")
        communities = cursor.fetchall()
        conn.close()

        total_claims = sum(c['total_claims'] for c in communities)
        total_approved = sum(c['total_approved'] for c in communities)
        total_rejected = sum(c['total_rejected'] for c in communities)
        total_in_process = sum(c['total_in_process'] for c in communities)
        total_delayed = sum(c['total_delayed'] for c in communities)

        return jsonify({
            "total_claims": total_claims,
            "total_approved": total_approved,
            "total_rejected": total_rejected,
            "total_in_process": total_in_process,
            "total_delayed": total_delayed
        })
    except Exception as e:
        return jsonify({"error": str(e)})

# ----------------------------
# API: Search by community
# ----------------------------
@app.route('/api/search')
def search_community():
    community_id = request.args.get("community_id")
    if not community_id:
        return jsonify({"error": "No community ID provided"}), 400
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.DOC_ID_NUMBER as id,
                   CONCAT('Document ', u.DOC_ID_NUMBER) as name,
                   u.document_status,
                   u.Community_ID
            FROM users u
            WHERE u.community_id = %s
        """, (community_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return jsonify({"error": "No documents found for this community"}), 404

        docs_by_status = {}
        for d in rows:
            status = d['document_status'] or "Claim"
            if status not in docs_by_status:
                docs_by_status[status] = []
            docs_by_status[status].append(d)

        return jsonify(docs_by_status)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/occupations')
def occupations():
    community_id = request.args.get('community_id')
    if not community_id:
        return jsonify({"error": "community_id is required"}), 400

    # Connect to DB
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get unique occupations for the community
    cursor.execute("SELECT DISTINCT Occupation FROM users WHERE Community_ID = %s", (community_id,))
    rows = cursor.fetchall()
    conn.close()

    occupations_list = [row['Occupation'] for row in rows if row['Occupation']]

    # Load schemes from JSON
    with open(os.path.join(BASE_DIR, "static", "scheme.json"), "r") as f:
        scheme_data = json.load(f)

    # Map occupation → schemes
    result = {}
    for occ in occupations_list:
        if occ in scheme_data:
            result[occ] = scheme_data[occ]
        else:
            result[occ] = []

    return jsonify(result)


# ----------------------------
# API: Serve single document JSON
# ----------------------------
@app.route('/api/document/<int:doc_id>')
def get_document(doc_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE DOC_ID_NUMBER = %s", (doc_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"error": "Document not found"}), 404

        return jsonify(row)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ----------------------------
# Run app
# ----------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
