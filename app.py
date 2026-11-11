"""ScoutIQ – Flask uygulamasının giriş noktası.

Uygulama burada kurulur; sayfalar routes/ klasöründeki Blueprint modüllerindedir:
  auth (giriş/kayıt) · players (arama, oyuncu) · reports (rapor/not) · history (arama geçmişi)
  watchlist (izleme listesi, en çok yıldızlananlar) · clubs · compare · quiz (kulüp bağlantısı oyunu) · admin
Çalıştırma:  python app.py  →  http://127.0.0.1:5000
"""
from flask import Flask

from config import SECRET_KEY
from routes import BLUEPRINTS
from utils import eur


def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"   # başka sitelerden gelen POST isteklerini (CSRF) engeller
    app.add_template_filter(eur, "eur")             # şablonlarda {{ değer|eur }} → €12.5M
    for bp in BLUEPRINTS:
        app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
