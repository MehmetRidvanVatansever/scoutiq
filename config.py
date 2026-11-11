"""Uygulama ayarları ve sabitler."""
import os

SECRET_KEY = os.getenv("SECRET_KEY", "scoutiq-gelistirme-anahtari")   # yayında SECRET_KEY ortam değişkeni tanımla
PER_PAGE = 25

# sıralama: URL'deki anahtar -> SQL sütunu (yalnızca bu sözlükteki sütunlar kullanılabilir = whitelist)
SORTS = {"value": "market_value_eur", "age": "age", "name": "name",
         "goals": "goals", "assists": "assists"}

DEFAULT_DIR = {"value": "desc", "age": "asc", "name": "asc",
               "goals": "desc", "assists": "desc"}

TOP_SORTS = {"stars": "star_count", "value": "market_value_eur", "age": "age", "name": "name"}

TOP_DIR = {"stars": "desc", "value": "desc", "age": "asc", "name": "asc"}


# arama geçmişi sayfasındaki filtre etiketleri
FILTER_LABELS = {"name": "Name", "country": "Country", "league": "League", "position": "Position",
                 "age_min": "Age ≥", "age_max": "Age ≤", "value_min": "Value ≥ (M€)",
                 "value_max": "Value ≤ (M€)"}

