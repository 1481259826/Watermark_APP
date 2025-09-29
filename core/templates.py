# core/templates.py
import json
from pathlib import Path
import os

APP_DIR = Path.home() / '.my_watermarker'
APP_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_FILE = APP_DIR / 'templates.json'

def load_templates():
    if not TEMPLATES_FILE.exists():
        return {}
    with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_templates(obj):
    with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
