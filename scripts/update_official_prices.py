"""Refresh only unambiguous prices visible in official Turkish brand price pages.

Rows that cannot be tied to a single model/trim and a single TRY amount are
left as-is. This avoids guessing when a site needs JavaScript or shows both a
campaign and list price in the same row.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
FEED_PATH = ROOT / "prices.json"
CATALOG_PATH = ROOT / "catalog.json"
REPORT_PATH = ROOT / "price-update-report.json"

SOURCES = {
    "Alfa Romeo": "https://www.alfaromeo.com.tr/configurator/",
    "Audi": "https://fiyatlistesi.audi.com.tr/",
    "BMW": "https://www.bmw.com.tr/tr/fastlane/bmw-fiyat-listesi.html",
    "BYD": "https://www.bydauto.com.tr/fiyat-listesi/",
    "Chery": "https://cherytr.com/modeller/",
    "Citroën": "https://talep.citroen.com.tr/fiyat-listesi",
    "Dacia": "https://www.dacia.com.tr/dacia-fiyat-listesi.html",
    "Fiat": "https://www.fiat.com.tr/kampanyalar",
    "Ford": "https://www.ford.com.tr/arac-olustur",
    "Honda": "https://www.honda.com.tr/otomobil/otomobil-fiyat-listesi-2025",
    "Hyundai": "https://www.hyundai.com/tr/tr/satis/fiyat-listesi.html",
    "Jeep": "https://www.jeep.com.tr/jeep-fiyat-listesi",
    "Kia": "https://www.kia.com/tr/fiyat-listesi.html",
    "Mercedes-Benz": "https://fiyat.mercedes-benz.com.tr/arac-karsilastirma-yazdir",
    "MG": "https://www.mg-turkey.com/tr/fiyat-listesi.html",
    "Nissan": "https://www.nissan.com.tr/fiyat-listesi/sifir-arac-fiyatlari-2026.html",
    "Opel": "https://fiyatlisteleri.opel.com.tr/binek-araclar",
    "Peugeot": "https://kampanya.peugeot.com.tr/fiyat-listesi/print.html",
    "Porsche": "https://www.porsche.com/turkey/tr/models/",
    "Renault": "https://www.renault.com.tr/renault-fiyat-listeleri/binek-arac-fiyat-listesi.html",
    "SEAT": "https://www.seat.com.tr/firsatlar/fiyat-listesi",
    "Škoda": "https://www.skoda.com.tr/fiyat-listesi",
    "Suzuki": "https://www.suzuki.com.tr/tr/otomobil/fiyat-listesi.html",
    "Tesla": "https://www.tesla.com/tr_tr/modely/design",
    "Togg": "https://togg.com.tr/price-list",
    "Toyota": "https://turkiye.toyota.com.tr/middle/fiyat-listesi/",
    "Volkswagen": "https://binekarac.vw.com.tr/tr/fiyat-listesi.html",
    "Volvo": "https://www.volvocars.com/tr/fiyat-listesi/",
}

PRICE_RE = re.compile(
    r"(?:₺\s*|\bTL\s*)(\d[\d.\s]*(?:,\d{1,2})?)"
    r"|(\d[\d.\s]*(?:,\d{1,2})?)\s*(?:₺|\bTL\b)",
    re.IGNORECASE,
)
ROW_SELECTORS = "tr, li, article, [class*=price-row], [class*=price-item], [class*=model-card]"


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def currency_values(text: str) -> list[int]:
    values = []
    for match in PRICE_RE.finditer(text):
        raw = (match.group(1) or match.group(2) or "").strip()
        digits = re.sub(r"[^0-9]", "", raw)
        if len(digits) >= 6:
            values.append(int(digits))
    return sorted(set(values))


def model_is_in_text(model: str, text: str) -> bool:
    model_text = normalize(model)
    haystack = f" {normalize(text)} "
    return bool(model_text) and f" {model_text} " in haystack


def parse_page(html: bytes) -> list[tuple[str, list[int]]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen = set()
    for element in soup.select(ROW_SELECTORS):
        text = " ".join(element.stripped_strings)
        normalized = normalize(text)
        if len(text) > 900 or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        values = currency_values(text)
        if values:
            rows.append((text, values))
    return rows


def download(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "OtoFiyatWeeklyPriceCheck/1.0 (public price list verifier)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=35) as response:
        return response.read()


def main() -> None:
    feed = json.loads(FEED_PATH.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    updated = []
    skipped = []
    unresolved = []
    page_rows: dict[str, list[tuple[str, list[int]]]] = {}

    for brand, url in SOURCES.items():
        try:
            page_rows[brand] = parse_page(download(url))
        except Exception as exc:  # one inaccessible source must not stop the run
            page_rows[brand] = []
            skipped.append({"brand": brand, "reason": f"source unavailable: {type(exc).__name__}"})
        time.sleep(0.4)

    for entry in catalog:
        brand, model = entry["brand"], entry["model"]
        model_key = f"{brand}|{model}"
        trims = feed.setdefault("prices", {}).get(model_key, [])
        rows = page_rows.get(brand, [])
        matching_rows = [(text, values) for text, values in rows if model_is_in_text(model, text)]
        if not trims:
            single_prices = {tuple(values) for _, values in matching_rows if len(values) == 1}
            if len(single_prices) == 1:
                price = next(iter(single_prices))[0]
                trim_name = "Resmî başlangıç fiyatı"
                feed["prices"][model_key] = [{"trim": trim_name, "price": price}]
                updated.append({"brand": brand, "model": model, "trim": trim_name, "old": None, "price": price})
            else:
                unresolved.append({"brand": brand, "model": model, "reason": "no unique model price in a public page row"})
            continue
        for trim in trims:
            trim_name = trim.get("trim", "")
            candidates = matching_rows
            if len(trims) > 1:
                candidates = [(text, vals) for text, vals in matching_rows if model_is_in_text(trim_name, text)]
            unique = {tuple(values) for _, values in candidates if len(values) == 1}
            if len(unique) != 1:
                unresolved.append({"brand": brand, "model": model, "trim": trim_name, "reason": "price row was missing or ambiguous"})
                continue
            price = next(iter(unique))[0]
            if price != trim.get("price"):
                old_price = trim.get("price")
                trim["price"] = price
                updated.append({"brand": brand, "model": model, "trim": trim_name, "old": old_price, "price": price})

    checked_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    feed["checkedAt"] = checked_at
    if updated:
        feed["updatedAt"] = checked_at
    FEED_PATH.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps({"checkedAt": checked_at, "updated": updated, "unresolved": unresolved, "skipped": skipped}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {len(updated)} price records; {len(skipped)} brand source pages were unavailable.")


if __name__ == "__main__":
    main()
