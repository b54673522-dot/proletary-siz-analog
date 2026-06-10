from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from matcher import extract_characteristics


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ProletaryAnalogBot/1.0; +https://github.com/b54673522-dot)"
}


def clean_text(value):
    return " ".join((value or "").split())


def extract_price(text):
    markers = ["руб", "₽", "р."]
    lowered = text.lower()
    if not any(marker in lowered for marker in markers):
        return ""
    return clean_text(text[:120])


def extract_article(text):
    lowered = text.lower()
    for marker in ["артикул", "арт.", "арт:"]:
        if marker in lowered:
            start = lowered.find(marker)
            fragment = text[start : start + 80]
            return clean_text(fragment.replace("Артикул", "").replace("арт.", "").replace("Арт.", "").replace(":", ""))
    return ""


def product_from_text(manufacturer, name, description, url):
    characteristics = extract_characteristics(f"{name} {description}")
    return {
        "manufacturer": manufacturer,
        "name": name,
        "article": extract_article(description),
        "category": characteristics.get("category") or "",
        "subcategory": characteristics.get("subcategory") or "",
        "product_type": characteristics.get("product_type") or "",
        "season": characteristics.get("season") or "",
        "composition": characteristics.get("composition") or "",
        "fabric_name": characteristics.get("fabric_name") or "",
        "fabric_density": characteristics.get("fabric_density") or "",
        "protective_properties": characteristics.get("protective_properties") or [],
        "sop": characteristics.get("sop") or "",
        "color": characteristics.get("color") or "",
        "description": description,
        "price": extract_price(description),
        "stock": "",
        "url": url,
    }


def looks_like_product_block(tag):
    class_text = " ".join(tag.get("class", [])).lower()
    id_text = (tag.get("id") or "").lower()
    marker_text = f"{class_text} {id_text}"
    markers = ["product", "catalog", "card", "item", "goods", "tovar", "tile"]
    return any(marker in marker_text for marker in markers)


def parse_catalog(manufacturer, catalog_url, max_products=80):
    response = requests.get(catalog_url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    products = []
    seen_urls = set()

    candidate_blocks = soup.find_all(looks_like_product_block)

    for block in candidate_blocks:
        link = block.find("a", href=True)
        title = (
            block.find(["h1", "h2", "h3", "h4"])
            or block.find(attrs={"class": lambda value: value and "title" in value.lower()})
            or link
        )
        name = clean_text(title.get_text(" ")) if title else ""
        description = clean_text(block.get_text(" "))
        url = urljoin(catalog_url, link["href"]) if link else catalog_url

        if not name or len(name) < 3 or url in seen_urls:
            continue
        if len(description) < len(name):
            description = name

        seen_urls.add(url)
        products.append(product_from_text(manufacturer, name, description, url))

        if len(products) >= max_products:
            return products

    if products:
        return products

    # Fallback for very simple catalog pages: collect useful links and headings.
    for link in soup.find_all("a", href=True):
        name = clean_text(link.get_text(" "))
        if len(name) < 5:
            continue
        url = urljoin(catalog_url, link["href"])
        if url in seen_urls:
            continue
        seen_urls.add(url)
        products.append(product_from_text(manufacturer, name, name, url))
        if len(products) >= max_products:
            break

    return products
