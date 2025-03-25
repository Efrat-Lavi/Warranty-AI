#!/bin/bash

# עדכון מערכת והתקנת תלויות עבור Tesseract
apt-get update
apt-get install -y tesseract-ocr libleptonica-dev g++ python3-dev pkg-config

# התקנה של התלויות של Python
pip install -r requirements.txt
