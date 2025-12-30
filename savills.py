import requests
import re
from bs4 import BeautifulSoup
from storage import load_existing, upsert_items, save_all

# =====================
# helpers
# =====================

def parse_int(text):
    if not text:
        return None
    t = re.sub(r"[^\d]", "", text)
    return int(t) if t else None

def parse_float(text):
    if not text:
        return None
    t = re.sub(r"[^\d.,]", "", text).replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None

def extract_images(card, base):
    urls = []
    for img in card.select("img.annonce_img"):
        if img.get("data-src"):
            urls.append(base + img["data-src"])
        elif img.get("src"):
            urls.append(base + img["src"])
    urls = list(dict.fromkeys(urls))
    return (urls[0] if urls else None, urls)

# =====================
# config
# =====================

SOURCE = {
    "id": "riviera_savills",
    "name": "Savills French Riviera",
    "logo": "savills.svg",
}

BASE = "https://riviera.savills.fr"
SEARCH_URL = BASE + "/en/buy/"
RESULTS_FILE = "results.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
}

# =====================
# scraper
# =====================

def scrape_savills_houses():
    session = requests.Session()
    existing_index = load_existing(RESULTS_FILE)

    # -------------------------------------------------
    # 1. INITIAL SEARCH (applies filters)
    # -------------------------------------------------
    session.post(
        SEARCH_URL,
        headers={**HEADERS, "Referer": SEARCH_URL},
        data={
            "transac": "Vente",
            "subsectors[]": [
                "SAINT_JEAN_CAP_FERRAT",
                "VILLEFRANCHE_SUR_MER",
                "EZE",
                "NICE",
                "CANNES",
                "THEOULE_SUR_MER",
                "MANDELIEU",
                "MOUGINS",
            ],
            "_types[]": "HOUSE",
            "min": "1500000",
            "max": "5000000",
            "new_research": "1",
            "ajax": "true",
        },
    )

    # -------------------------------------------------
    # 2. PAGINATION (POST + URL /p=N)
    # -------------------------------------------------
    page = 1
    seen_ids = set()
    scraped = []

    while True:
        url = f"{SEARCH_URL}p={page}?ajax=true&tri=id:DESC"
        r = session.post(
            url,
            headers={**HEADERS, "Referer": SEARCH_URL},
            data={"ajax": "true", "no_redirect": "true"},
        )

        if r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "lxml")
        cards = soup.select("div.annonce")

        if not cards:
            print(f"⛔ No listings on page {page}, stopping.")
            break

        page_ids = []

        for card in cards:
            sel = card.select_one(".jsUpdateSelection")
            listing_id = parse_int(sel["data-id"]) if sel else None

            if not listing_id or listing_id in seen_ids:
                continue

            seen_ids.add(listing_id)
            page_ids.append(listing_id)

            link = card.select_one("a[href]")
            url = BASE + link["href"] if link else None

            city_el = card.select_one(".infos .city")
            city = city_el.get_text(strip=True) if city_el else None

            type_el = card.select_one(".group_infos .type")
            surface_el = card.select_one(".surface .chiffre")
            bedrooms_el = card.select_one(".chambre .chiffre")
            price_el = card.select_one(".price")

            image_primary, images = extract_images(card, BASE)

            scraped.append({
                "source": SOURCE,
                "id": listing_id,
                "url": url,
                "city": city,
                "type": type_el.get_text(strip=True) if type_el else None,
                "system_category": "house",
                "surface_m2": parse_float(surface_el.get_text()) if surface_el else None,
                "rooms": None,
                "bedrooms": parse_int(bedrooms_el.get_text()) if bedrooms_el else None,
                "price_eur": parse_int(price_el.get_text()) if price_el else None,
                "price_text": price_el.get_text(strip=True) if price_el else None,
                "image_primary": image_primary,
                "images": images,
            })

        print(f"✅ Savills page {page} parsed ({len(page_ids)} listings)")
        print(f"   IDs: {page_ids}")

        if not page_ids:
            print("⛔ No new IDs found, stopping.")
            break

        page += 1

    # -------------------------------------------------
    # 3. UPSERT + SAVE
    # -------------------------------------------------
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
    scrape_savills_houses()