#!/usr/bin/env bash

# עדכון חבילות והתקנה של leptonica ו-Tesseract
apt-get update
apt-get install -y \
  tesseract-ocr \
  libleptonica-dev \
  g++ \
  pkg-config \
  python3-dev

# התקנת חבילות Python
pip install -r requirements.txt
