import requests
import re
from bs4 import BeautifulSoup
from storage import load_existing, upsert_items, save_all

# =====================
# helpers
# =====================

def parse_int(text: str):
    if not text:
        return None
    m = re.search(r"\d+", text.replace(" ", ""))
    return int(m.group(0)) if m else None

def parse_float(text: str):
    if not text:
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", text)
    if not m:
        return None
    return float(m.group(0).replace(",", "."))

def extract_city_from_h3(text: str):
    # "Sale Apartment Cannes" → Cannes
    if not text:
        return None
    parts = text.split()
    return parts[-1] if len(parts) >= 2 else None

def extract_type_from_h3(text: str):
    # "Sale Apartment Cannes" → apartment
    if not text:
        return None
    parts = text.split()
    return parts[1].lower() if len(parts) >= 2 else None

def extract_metric(card, icon_name):
    img = card.find("img", src=lambda s: s and icon_name in s)
    if not img:
        return None
    li = img.find_parent("li")
    if not li:
        return None
    span = li.find("span")
    return span.get_text(" ", strip=True) if span else None

def extract_rooms_from_title(title: str):
    # "4 rooms" / "4-room"
    if not title:
        return None
    m = re.search(r"\b(\d+)\s*[- ]?\s*rooms?\b", title.lower())
    return int(m.group(1)) if m else None

# =====================
# source config
# =====================

SOURCE = {
    "id": "michael_zingraf",
    "name": "Michaël Zingraf Real Estate",
    "logo": "michael.svg",
}

RESULTS_FILE = "results.json"

BASE_SEARCH_URL = (
    "https://www.michaelzingraf.com/en/search"
    "?category=1"
    "&region=1"
    "&sector=2,27,24,25"
    "&price=-2000000"
    "&subtype=5"
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

            h3 = card.select_one("h3")
            h3_text = h3.get_text(strip=True) if h3 else None

            city = extract_city_from_h3(h3_text)
            raw_type = extract_type_from_h3(h3_text)

            price_el = card.select_one("span.text-redmz")
            price_text = price_el.get_text(strip=True) if price_el else None
            price_eur = parse_int(price_text)

            surface_text = extract_metric(card, "area.svg")
            bedrooms_text = extract_metric(card, "bedroom.svg")

            surface_m2 = parse_float(surface_text)
            bedrooms = parse_int(bedrooms_text)
            rooms = extract_rooms_from_title(title)

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
                "city": city,

                "system_category": "apartment",
                "type": raw_type,

                "surface_m2": surface_m2,
                "rooms": rooms,
                "bedrooms": bedrooms,

                "price_eur": price_eur,
                "price_text": price_text,

                "image_primary": images[0] if images else None,
                "images": images,
            })

        print(f"✅ Zingraf apartments page {page} parsed")
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