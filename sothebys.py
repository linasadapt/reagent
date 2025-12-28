import requests
import re
from bs4 import BeautifulSoup
from storage import load_existing, upsert_items, save_all

# =====================
# parsing helpers
# =====================

def parse_float(text: str):
    if not text:
        return None
    t = text.strip().replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None

def parse_int(text: str):
    if not text:
        return None
    t = re.sub(r"[^\d]", "", text)
    return int(t) if t else None

def parse_price_eur(price_text: str):
    return parse_int(price_text) if price_text else None

def extract_images(img_tag, base_url):
    if not img_tag:
        return {"primary": None, "all": []}

    urls = []

    srcset = img_tag.get("data-srcset") or img_tag.get("srcset")
    if srcset:
        for part in srcset.split(","):
            url = part.strip().split(" ")[0]
            urls.append(base_url + url)

    if not urls:
        if img_tag.get("data-src"):
            urls.append(base_url + img_tag["data-src"])
        elif img_tag.get("src"):
            urls.append(base_url + img_tag["src"])

    urls = list(dict.fromkeys(urls))
    return {
        "primary": urls[-1] if urls else None,
        "all": urls,
    }

# =====================
# config
# =====================

SOURCE = {
    "id": "cotedazur_sothebys",
    "name": "Côte d’Azur Sotheby’s International Realty",
    "logo": "cotedazur-sothebys.png",
}

BASE = "https://www.cotedazur-sothebysrealty.com"
SEARCH_URL = BASE + "/en/sale/"
RESULTS_FILE = "results.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
}

# =====================
# load existing storage
# =====================

existing_index = load_existing(RESULTS_FILE)

# =====================
# session + search init
# =====================

session = requests.Session()
session.get(SEARCH_URL + "?new_research=1", headers={"User-Agent": "Mozilla/5.0"})

session.post(
    SEARCH_URL,
    headers={**HEADERS, "Referer": SEARCH_URL + "?new_research=1"},
    data={
        "ajax": "true",
        "form_post": "1",

        # price range (APARTMENTS)
        "min": "500000",
        "max": "1500000",

        # multi-city
        "geo_multi[]": [
            "FR;06400;cannes",
            "FR;06000;nice",
            "FR;06300;nice",
            "FR;06590;theoule-sur-mer",
            "FR;06250;mougins",
            "FR;06230;villefranche-sur-mer",
            "FR;06230;st-jean-cap-ferrat",
            "FR;06210;mandelieu-la-napoule",
            "FR;06360;eze",
        ],

        "flagval_cities": (
            "FR;06400;cannes#"
            "FR;06000;nice#"
            "FR;06300;nice#"
            "FR;06590;theoule-sur-mer#"
            "FR;06250;mougins#"
            "FR;06230;villefranche-sur-mer#"
            "FR;06230;st-jean-cap-ferrat#"
            "FR;06210;mandelieu-la-napoule#"
            "FR;06360;eze#"
        ),

        "flagval_categories": "Appartment#",
        "category[]": "Appartment",
        "flagval_current_map": "map",
    },
)

# =====================
# pagination + parsing
# =====================

page = 1
max_pages = None
new_results = []

while True:
    r = session.get(
        SEARCH_URL,
        params={"ajax": "true", "tri": "id:DESC", "p": page},
        headers={**HEADERS, "Referer": SEARCH_URL},
    )

    html = r.text

    if page == 1:
        m = re.search(r'data-page-count="(\d+)"', html)
        if not m:
            raise RuntimeError("Could not determine page count")
        max_pages = int(m.group(1))
        print(f"Total pages to fetch: {max_pages}")

    soup = BeautifulSoup(html, "lxml")

    for card in soup.select("div.annonce"):
        img_tag = card.select_one("img.annonce_img")
        images = extract_images(img_tag, BASE)

        link = card.select_one("a[href]")
        infos = card.select_one("div.infos")
        infos_bottom = card.select_one("div.infos_bottom")

        city = infos.select_one("span.city").get_text(strip=True) if infos else None
        sel = infos.select_one(".jsUpdateSelection") if infos else None
        listing_id = sel.get("data-id") if sel else None

        type_el = infos_bottom.select_one("span.type") if infos_bottom else None
        surface_el = infos_bottom.select_one("span.surface span.chiffre") if infos_bottom else None
        rooms_el = infos_bottom.select_one("span.pieces span.chiffre") if infos_bottom else None
        bedrooms_el = infos_bottom.select_one("span.chambre span.chiffre") if infos_bottom else None
        price_el = infos_bottom.select_one("span.price") if infos_bottom else None

        price_text = price_el.get_text(" ", strip=True) if price_el else None

        new_results.append({
            "source": SOURCE,
            "id": parse_int(listing_id) if listing_id else None,
            "url": BASE + link["href"] if link else None,
            "city": city,
            "system_category": "appartment",
            "type": type_el.get_text(strip=True) if type_el else None,
            "surface_m2": parse_float(surface_el.get_text(strip=True)) if surface_el else None,
            "rooms": parse_int(rooms_el.get_text(strip=True)) if rooms_el else None,
            "bedrooms": parse_int(bedrooms_el.get_text(strip=True)) if bedrooms_el else None,
            "price_eur": parse_price_eur(price_text),
            "price_text": price_text,
            "image_primary": images["primary"],
            "images": images["all"],
        })

    print(f"✅ Page {page} parsed")

    if page >= max_pages:
        break

    page += 1

# =====================
# upsert + persist
# =====================

added, updated = upsert_items(existing_index, new_results)
save_all(RESULTS_FILE, existing_index)

print(f"\nDONE")
print(f"Added: {added}")
print(f"Updated: {updated}")
print(f"Total stored: {len(existing_index)}")