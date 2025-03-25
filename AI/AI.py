import os
import requests
import fitz  # PyMuPDF - חילוץ טקסט מ-PDF
import pytesseract  # OCR לזיהוי טקסט מתמונות
from PIL import Image, ImageEnhance, ImageFilter
from io import BytesIO
from openai import OpenAI
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from dotenv import load_dotenv

load_dotenv()  # טוען משתנים מקובץ .env
api_key = os.getenv('OPENAI_API_KEY')

if not api_key:
    raise ValueError("Missing OPENAI_API_KEY environment variable")

# יש להגדיר את הנתיב של Tesseract אם נדרש (למשתמשי Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

app = Flask(__name__)
CORS(app)  # מאפשר לכל הדומיינים לקרוא ל-API

client = OpenAI()
my_model = "gpt-4o-mini"

# פרומפטים
VERIFY_PROMPT = """Analyze the following text and determine if it represents a warranty certificate. 
Respond only with 'yes' or 'no' (no extra words, explanations, or formatting).
Text:
"""

EXTRACTION_PROMPT = EXTRACTION_PROMPT = """You are an AI that extracts warranty certificate details. 
Always return **ONLY** a valid JSON object with the following structure, **without any extra text**:
{
    "product_name": "Product Name",
    "company_name": "Company Name",
    "expiration_date": "YYYY-MM-DD"
}
If a field is missing, set its value to null.
Respond **only** with the JSON object (nothing else)."""

def clean_and_convert_quotes(text):

    # מחליף את כל הגרשים הלא תקניים במרכאות כפולות רגילות
    text = text.replace( "'",'׳')  # משנה את הגרש (׳) לגרש תקני (')
    text = text.replace( '"','״')  # משנה את הגרש הכפול (״) לגרש כפול רגיל (")
    return text

def download_file(url):
    """ מוריד קובץ מה-URL """
    try:
        response = requests.get(url, timeout=10)  # מגביל את זמן ההורדה
        response.raise_for_status()
        
        content_type = response.headers.get('Content-Type', '').lower()
        return BytesIO(response.content), content_type
    except requests.exceptions.RequestException as e:
        return None, str(e)

def extract_text_from_pdf(file_stream):
    """ חילוץ טקסט מקובץ PDF """
    text = ""
    try:
        doc = fitz.open(stream=file_stream, filetype="pdf")
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def enhance_image(image):
    """ שיפור תמונה לקריאה טובה יותר ב-OCR """
    image = image.convert("L")  # המרה לשחור-לבן
    image = image.filter(ImageFilter.SHARPEN)  # חידוד התמונה
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)  # הגברת ניגודיות
    return image

def extract_text_from_image(file_stream):
    """ חילוץ טקסט מתמונה באמצעות OCR """
    try:
        image = Image.open(file_stream)
        image = enhance_image(image)  # שיפור הקריאות
        text = pytesseract.image_to_string(image, lang="heb+eng")  # תמיכה בעברית ואנגלית
        return clean_and_convert_quotes(text.strip())
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def query_ai(prompt):
    """ שליחת פרומפט ל-GPT וקבלת תשובה """
    try:
        completion = client.chat.completions.create(
            model=my_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Error querying AI: {str(e)}"
    

@app.route('/generate', methods=['POST'])
def generate():
    data = request.get_json()
    
    if not data or 'file_url' not in data:
        return jsonify({'error': 'Missing file URL'}), 400

    file_url = data['file_url']
    file_stream, content_type = download_file(file_url)

    if file_stream is None:
        return jsonify({'error': f'Failed to download file: {content_type}'}), 400

    # זיהוי סוג הקובץ מה-Content-Type
    if 'pdf' in content_type:
        extracted_text = extract_text_from_pdf(file_stream)
    elif 'image' in content_type or any(ext in file_url.lower() for ext in ['.jpg', '.jpeg', '.png']):
        extracted_text = extract_text_from_image(file_stream)
    else:
        return jsonify({'error': 'Unsupported file type'}), 400

    # טיפול בשגיאות או טקסט ריק
    if not extracted_text or "Error" in extracted_text:
        return jsonify({'error': 'Failed to extract text'}), 400

    # שליחת הטקסט ל-AI לבדיקה האם זה תעודת אחריות
    verification_prompt = f"{VERIFY_PROMPT}\n{extracted_text}"
    is_warranty = query_ai(verification_prompt).lower()

    if is_warranty != "yes":
        return jsonify({'message': "הקובץ לא מזוהה כתעודת אחריות"}), 400

    # אם זה אכן תעודת אחריות, שולחים לניתוח
    full_prompt = f"{EXTRACTION_PROMPT}\n\nExtract the warranty details from the following text:\n{extracted_text}"
    response_text = query_ai(full_prompt)

    return response_text

if __name__ == '__main__':
    os.makedirs("uploads", exist_ok=True)  # יצירת תיקייה אם לא קיימת
    app.run(host='0.0.0.0', port=5000)
