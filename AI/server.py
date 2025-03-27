from flask import Flask, request, jsonify
import base64
import requests
from io import BytesIO
from PIL import Image
from openai import OpenAI
import fitz  # PyMuPDF
from flask_cors import CORS
import os
from dotenv import load_dotenv
import json
load_dotenv() 
api_key = os.getenv('OPENAI_API_KEY')

if not api_key:
    raise ValueError("Missing OPENAI_API_KEY environment variable")

app = Flask(__name__)
CORS(app) 
client = OpenAI()

VERIFY_PROMPT = """Analyze the following text and determine if it represents a warranty certificate or a recipt. 
Respond only with 'yes' or 'no' (no extra words, explanations, or formatting).
Text:
"""

PRONPT = """
You are an AI that extracts warranty certificate details. 
Always return **ONLY** a valid JSON object with the following structure, **without any extra text, explanations, or formatting**:
{
    "product_name": "Product Name",
    "company_name": "Company Name",
    "expiration_date": "YYYY-MM-DD"
}
If the expiration date is missing but a purchase date is found, set the expiration date to one year after the purchase date.
If another field is missing, set its value to null.
Your response **MUST begin with '{' and end with '}'** with no additional text.
Extract the warranty details from the attached file.
"""

my_model = "gpt-4o"

def download_and_encode_image(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    img = Image.open(BytesIO(response.content))
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def download_and_encode_pdf(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    doc = fitz.open(stream=response.content, filetype="pdf")
    page = doc.load_page(0)
    pix = page.get_pixmap()
    img_bytes = pix.tobytes("png")
    buffered = BytesIO(img_bytes)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def query_ai(base64_image):
    response = client.chat.completions.create(
        model=my_model,
        messages=[
            {"role": "system", "content": "You are an AI that extracts warranty certificate details."},
            {"role": "user", "content": [
                {"type": "text", "text": PRONPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
            ]},
        ],
    )
    raw_response = response.choices[0].message.content.strip()
    
    try:
        return json.loads(raw_response)  # המרה לאובייקט JSON אמיתי
    except json.JSONDecodeError:
        return None

def verify_ai(base64_image):
    response = client.chat.completions.create(
        model=my_model,
        messages=[
            {"role": "user", "content": "You are an AI that checks if the document is a warranty"},
            {"role": "user", "content": [
                {"type": "text", "text": VERIFY_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}},
            ]},
        ],
    )
    return response.choices[0].message.content

@app.route("/generate", methods=["POST"])
def process_file():
    data = request.json
    file_url = data.get("file_url")
    if not file_url:
        return jsonify({"error": "Missing file_url"}), 400
    
    try:
        if ".pdf" in file_url.lower():
            base64_image = download_and_encode_pdf(file_url)
        elif any(ext in file_url.lower() for ext in ['.jpg', '.jpeg', '.png']):
            base64_image = download_and_encode_image(file_url)
        else:
            return jsonify({"error": "Unsupported file type"}), 400
        
        is_warranty = verify_ai(base64_image).lower()
        if is_warranty == "yes":
            response_text = query_ai(base64_image)
            return response_text
        else:
            return jsonify({"error": "Not a warranty document"}),400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
