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
import config   # your config.py with api_key

# configure Gemini
genai.configure(api_key=config.api_key)

# configure MySQL
db_config = {
    "host": "localhost",       # update if needed
    "user": "root",            # update with your MySQL user
    "password": "Abhishek@21", # update with your MySQL password
    "database": "fra_claims"   # update with your DB name
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
CORS(app)

# --------- PDF -> English using Gemini ----------
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


# --------- Geolocation helper ----------
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
            return {"lat": results[0]["lat"], "lon": results[0]["lon"]}
    except Exception as e:
        print("Geocode error:", e)
    return {"lat": None, "lon": None}


# --------- Insert into MySQL ----------
def insert_claim_to_db(claim):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Step 1: Ensure Community exists
        cursor.execute("SELECT Community_ID FROM communities WHERE Community_Name = %s", (claim.get("Community_Name"),))
        result = cursor.fetchone()

        if result:
            community_id = result[0]
        else:
            # Insert new community with dummy lat/lon if not available
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

        # Step 2: Insert into users
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

        # Step 3: Update community counters
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
            # default only total_claims if status invalid
            cursor.execute("""
                UPDATE communities
                SET total_claims = total_claims + 1
                WHERE Community_ID = %s
            """, (community_id,))

        conn.commit()
        cursor.close()
        conn.close()
        print("Inserted into DB and updated community counters successfully.")
        return True
    except Exception as e:
        print("DB insert error:", e)
        return False


# --------- Routes ----------
@app.route("/")
def index():
    return render_template("upload.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No selected file"}), 400

    # Save uploaded file
    safe_name = file.filename
    save_path = os.path.join(UPLOAD_FOLDER, safe_name)
    file.save(save_path)
    print(f"Saved uploaded file to: {save_path}")

    # Process the file (translate + extract)
    translated_text = translate_pdf_to_english(save_path)
    if not translated_text.strip():
        return jsonify({"success": False, "message": "No extractable text found in PDF."}), 400

    # Extraction prompt (matches DB fields)
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

    # Add unique IDs & location
    claim["DOC_ID_NUMBER"] = int(str(uuid.uuid4().int)[:8])
    claim["Location"] = get_location(
        claim.get("village_name"),
        claim.get("tehsil_name"),
        claim.get("district_name")
    )

    # Save JSON locally
    out_name = f"{claim['DOC_ID_NUMBER']}.json"
    out_path = os.path.join(UPLOAD_FOLDER, out_name)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(claim, f, ensure_ascii=False, indent=2)
    print(f"Saved processed JSON to: {out_path}")

    # Insert into MySQL
    db_status = insert_claim_to_db(claim)

    return jsonify({
        "success": True,
        "message": f"Processed and saved as {out_name} (DB insert: {'ok' if db_status else 'failed'})",
        "data": claim
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
