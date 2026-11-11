"""Sayfa modülleri (Flask Blueprint). Her modül kendi adresleriyle ilgili yönlendirmeleri içerir."""
from routes import auth, players, reports, history, watchlist, clubs, compare, quiz, admin

BLUEPRINTS = [auth.bp, players.bp, reports.bp, history.bp, watchlist.bp, clubs.bp, compare.bp, quiz.bp, admin.bp]
