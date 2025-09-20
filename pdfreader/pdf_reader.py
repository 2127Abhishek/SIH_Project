import google.generativeai as genai
from pypdf import PdfReader
import config
import requests
import json
import uuid
import re

# ------------------------------
# Configure Gemini API
# ------------------------------
api_key = config.api_key
genai.configure(api_key=api_key)

# ------------------------------
# Function to fetch location
# ------------------------------
def get_location(village, taluka, district):
    if not village or not taluka or not district:
        return {"lat": None, "lon": None}

    query = f"{village}, {taluka}, {district}, India"
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "Mozilla/5.0"}  # required by Nominatim
    try:
        response = requests.get(url, params={"q": query, "format": "json"}, headers=headers)
        results = response.json()
        if results:
            return {"lat": results[0]["lat"], "lon": results[0]["lon"]}
    except Exception as e:
        print("Error fetching location:", e)
    return {"lat": None, "lon": None}

# ------------------------------
# Read PDF text
# ------------------------------
pdf_path = "file.pdf"
reader = PdfReader(pdf_path)
pdf_text = "".join([page.extract_text() + "\n" for page in reader.pages if page.extract_text()])

if not pdf_text.strip():
    raise ValueError("PDF contains no extractable text.")

# ------------------------------
# Prompt Gemini for structured data (single claim)
# ------------------------------
prompt = f"""
Extract the following information from the text below and return ONLY a single dictionary:
{{"ID_Number": "generate a unique numeric id","Community":"<community>","Gender":"<gender>","Village": "<village>", "Taluka": "<taluka>", "District": "<district>", "Claim_Person": "<name>"}}

Text:
{pdf_text}
"""

# ------------------------------
# Call Gemini
# ------------------------------
response = genai.GenerativeModel("gemini-1.5-flash").generate_content(prompt)
raw_output = response.text.strip()

# ------------------------------
# Clean triple backticks (Markdown) if present
# ------------------------------
clean_output = re.sub(r"```(?:json)?", "", raw_output).strip()

# ------------------------------
# Parse JSON safely
# ------------------------------
try:
    claim = json.loads(clean_output)  # now a single dictionary
except json.JSONDecodeError as e:
    print("Failed to parse JSON:", e)
    claim = {}

# ------------------------------
# Add unique ID and location
# ------------------------------
claim["ID_Number"] = str(uuid.uuid4().int)[:8]  # 8-digit unique number
claim["Location"] = get_location(claim.get("Village"), claim.get("Taluka"), claim.get("District"))

# ------------------------------
# Save JSON file using Claim_Person name
# ------------------------------
claim_person = claim.get("ID_Number", "unknown").replace(" ", "_")  # replace spaces with underscores
file_name = f"{claim_person}.json"

with open(file_name, "w", encoding="utf-8") as f:
    json.dump(claim, f, ensure_ascii=False, indent=4)

print(f"Final JSON saved to {file_name} in pretty format")

