"""Ortak yardımcı fonksiyonlar: filtre / sıralama ayrıştırma, para biçimi, değer grafiği."""
from datetime import date

from flask import request

from config import SORTS, DEFAULT_DIR


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_sort(sorts=SORTS, defaults=DEFAULT_DIR, default="value"):
    """URL'deki sort ve dir değerlerini doğrular (izin verilmeyen değer varsayılana döner)."""
    sort = request.args.get("sort", default)
    if sort not in sorts:
        sort = default
    direction = request.args.get("dir", defaults[sort])
    if direction not in ("asc", "desc"):
        direction = defaults[sort]
    return sort, direction


def filter_sql(f):
    """Filtre sözlüğünü (name, country, league, position, age_min/max, value_min/max)
    WHERE koşullarına çevirir. Arama, kulüp ve admin sayfaları ortak kullanır."""
    where, params = [], []
    if f.get("name"):
        where.append("name ILIKE %s"); params.append(f"%{f['name']}%")
    for key, col in (("country", "country"), ("league", "league"), ("position", "main_position")):
        if f.get(key):
            where.append(f"{col} = %s"); params.append(f[key])
    # yaş, doğum tarihine çevrilir ki idx_players_birth indeksi kullanılabilsin:
    # yaş >= a  <=>  doğum <= bugün - a yıl      yaş <= b  <=>  doğum > bugün - (b+1) yıl
    n = num(f.get("age_min"))
    if n is not None:
        where.append("date_of_birth <= current_date - make_interval(years => %s)"); params.append(int(n))
    n = num(f.get("age_max"))
    if n is not None:
        where.append("date_of_birth > current_date - make_interval(years => %s)"); params.append(int(n) + 1)
    for key, cond in (("value_min", "market_value_eur >= %s"), ("value_max", "market_value_eur <= %s")):
        n = num(f.get(key))
        if n is not None:
            where.append(cond); params.append(n * 1_000_000)   # milyon € -> €
    return where, params


def safe_next(default):
    n = request.form.get("next", "")
    return n if n.startswith("/") and not n.startswith("//") else default


def eur(v):
    if v is None:
        return "-"
    if v >= 1_000_000:
        return f"€{v / 1_000_000:.1f}M"
    if v >= 1000:
        return f"€{v / 1000:.0f}K"
    return f"€{v}"


def value_chart(values, w=640, h=200, pad=30):
    """Değer geçmişini SVG çizgi grafiği için noktalara çevirir (harici kütüphane gerekmez)."""
    if len(values) < 2:
        return None
    t0 = values[0]["valued_at"].toordinal()
    span = max(1, values[-1]["valued_at"].toordinal() - t0)
    vmax = max(r["market_value_eur"] for r in values) or 1
    pts = [{"x": round(pad + (r["valued_at"].toordinal() - t0) / span * (w - 2 * pad), 1),
            "y": round(h - pad - r["market_value_eur"] / vmax * (h - 2 * pad), 1),
            "label": f"{r['valued_at'].strftime('%d.%m.%Y')}: {eur(r['market_value_eur'])}"
                     + (f" ({r['club']})" if r["club"] else "")} for r in values]
    years = sorted({r["valued_at"].year for r in values})
    step = max(1, len(years) // 8)
    ticks = [{"x": round(pad + (date(y, 1, 1).toordinal() - t0) / span * (w - 2 * pad), 1), "year": y}
             for y in years[::step] if date(y, 1, 1).toordinal() >= t0]
    return {"w": w, "h": h, "pad": pad, "points": pts, "ticks": ticks, "max": eur(vmax),
            "line": " ".join(f"{p['x']},{p['y']}" for p in pts)}

