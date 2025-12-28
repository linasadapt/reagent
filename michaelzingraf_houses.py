import requests
import re
from bs4 import BeautifulSoup
from storage import load_existing, upsert_items, save_all

# =====================
# helpers (same style as main scraper)
# =====================

def parse_int(text: str):
    if not text:
        return None
    t = re.sub(r"[^\d]", "", text)
    return int(t) if t else None

def parse_float(text: str):
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None

# =====================
# source config
# =====================

SOURCE = {
    "id": "michael_zingraf",
    "name": "Michaël Zingraf Real Estate",
    "logo": "michael-zingraf.png",
}

RESULTS_FILE = "results.json"

BASE_SEARCH_URL = (
    "https://www.michaelzingraf.com/en/search"
    "?category=1"
    "&region=1"
    "&sector=2,24,25,27"
    "&subtype=18,14"
    "&price=2000000/5000000"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
}

# =====================
# main scraper
# =====================

def scrape_zingraf_apartments():
    session = requests.Session()
    existing_index = load_existing(RESULTS_FILE)

    page = 1
    scraped = []

    while True:
        url = BASE_SEARCH_URL + f"&page={page}"
        r = session.get(url, headers=HEADERS)

        if r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "lxml")
        cards = soup.select("div[data-product_id]")

        if not cards:
            break

        for card in cards:
            listing_id = parse_int(card.get("data-product_id"))

            link_el = card.select_one("a[href]")
            url = link_el["href"] if link_el else None

            title_el = card.select_one("h2")
            title = title_el.get_text(strip=True) if title_el else None

            price_el = card.select_one("span.text-redmz")
            price_text = price_el.get_text(strip=True) if price_el else None
            price_eur = parse_int(price_text)

            surface_el = card.select_one("img[src*='area.svg'] + span")
            surface_m2 = parse_float(surface_el.get_text()) if surface_el else None

            bedrooms_el = card.select_one("img[src*='bedroom.svg'] + span")
            bedrooms = parse_int(bedrooms_el.get_text()) if bedrooms_el else None

            # images
            images = []

            bg = card.select_one("div[style*='background-image']")
            if bg:
                m = re.search(r"url\('([^']+)'\)", bg.get("style", ""))
                if m:
                    images.append(m.group(1))

            for img in card.select("img[src*='/storage/properties/']"):
                images.append(img["src"])

            images = list(dict.fromkeys(images))

            scraped.append({
                "source": SOURCE,
                "id": listing_id,
                "url": url,
                "title": title,
                "city": None,  # resolved later from detail page if needed
                "raw_category": "apartment",
                "system_category": "apartment",
                "surface_m2": surface_m2,
                "rooms": None,
                "bedrooms": bedrooms,
                "price_eur": price_eur,
                "price_text": price_text,
                "image_primary": images[0] if images else None,
                "images": images,
            })

        print(f"✅ Zingraf page {page} parsed")
        page += 1

    added, updated = upsert_items(existing_index, scraped)
    save_all(RESULTS_FILE, existing_index)

    print("\nDONE")
    print(f"Added: {added}")
    print(f"Updated: {updated}")
    print(f"Total stored: {len(existing_index)}")


# =====================
# entrypoint
# =====================

if __name__ == "__main__":
    scrape_zingraf_apartments()