import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from matcher import extract_characteristics


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ProletaryAnalogBot/1.0; +https://github.com/b54673522-dot)"
}


def clean_text(value):
    return " ".join((value or "").split())


def extract_price(text):
    match = re.search(r"(\d[\d\s]*[,.]?\d*)\s*(?:₽|руб|р\.)", text, re.IGNORECASE)
    if match:
        return clean_text(f"{match.group(1)} ₽")
    if "цена" not in text.lower():
        return ""
    return clean_text(text[:120])


def extract_article(text):
    explicit = re.search(r"(?:артикул|арт\.?)\s*:?\s*([A-Za-zА-Яа-я0-9-]+)", text, re.IGNORECASE)
    if explicit:
        return explicit.group(1)

    fallback = re.search(r"\b(\d{6,10})\b", text)
    if fallback:
        return fallback.group(1)
    return ""


def extract_stock(text):
    match = re.search(r"Доступно:?\s*([\d\s]+)\s*шт", text, re.IGNORECASE)
    if match:
        return clean_text(f"{match.group(1)} шт")
    match = re.search(r"([\d\s]+)\s*(?:шт\.|ед\.\s*осталось)", text, re.IGNORECASE)
    if match:
        return clean_text(f"{match.group(1)} шт")
    return ""


def extract_characteristic_value(text, label):
    pattern = rf"{re.escape(label)}:\s*(.+?)(?=\s+[А-ЯЁA-Z][А-ЯЁA-Zа-яёA-Za-z\s/().-]{{2,}}:|$)"
    match = re.search(pattern, text)
    if match:
        return clean_text(match.group(1))
    return ""


def product_from_text(manufacturer, name, description, url, article="", price="", stock=""):
    characteristics = extract_characteristics(f"{name} {description}")
    return {
        "manufacturer": manufacturer,
        "name": name,
        "article": article or extract_article(description),
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
        "price": price or extract_price(description),
        "stock": stock or extract_stock(description),
        "url": url,
    }


def product_from_fakel_card(manufacturer, url, soup):
    text = clean_text(soup.get_text(" "))
    title = soup.find("h1")
    name = clean_text(title.get_text(" ")) if title else ""
    article = extract_article(text)
    price = extract_price(text)
    stock = extract_stock(text)

    material = extract_characteristic_value(text, "Основной материал")
    kit = extract_characteristic_value(text, "Комплектность")
    protection = extract_characteristic_value(text, "Защитные свойства")
    sop = extract_characteristic_value(text, "Наличие СОП")
    insulation = extract_characteristic_value(text, "Утеплитель")
    climate = extract_characteristic_value(text, "Климатический пояс")

    description_parts = [
        name,
        f"Комплектность: {kit}" if kit else "",
        f"Основной материал: {material}" if material else "",
        f"Защитные свойства: {protection}" if protection else "",
        f"Наличие СОП: {sop}" if sop else "",
        f"Утеплитель: {insulation}" if insulation else "",
        f"Климатический пояс: {climate}" if climate else "",
        text,
    ]
    description = clean_text(" ".join(part for part in description_parts if part))
    return product_from_text(manufacturer, name, description, url, article, price, stock)


def product_from_fakel_catalog_row(manufacturer, url, name, row_text):
    description = clean_text(f"{name} {row_text}")
    return product_from_text(
        manufacturer=manufacturer,
        name=name,
        description=description,
        url=url,
        article=extract_article(row_text),
        price=extract_price(row_text),
        stock=extract_stock(row_text),
    )


def collect_fakel_products_from_soup(manufacturer, catalog_url, soup, max_products):
    products = []
    seen_urls = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/catalog/item-" not in href:
            continue

        url = urljoin(catalog_url, href)
        if url in seen_urls:
            continue

        name = clean_text(link.get_text(" "))
        if len(name) < 8:
            continue

        row_text = nearest_useful_text(link)
        products.append(product_from_fakel_catalog_row(manufacturer, url, name, row_text))
        seen_urls.add(url)

        if len(products) >= max_products:
            break

    return products


def collect_fakel_category_urls(catalog_url, soup):
    urls = []
    for link in soup.find_all("a", href=True):
        url = urljoin(catalog_url, link["href"])
        path = urlparse(url).path
        if url in urls:
            continue
        if "/catalog/" not in path or "/catalog/item-" in path:
            continue
        if path.rstrip("/") == urlparse(catalog_url).path.rstrip("/"):
            continue
        urls.append(url)
    return urls


def parse_fakel_catalog(manufacturer, catalog_url, soup, max_products):
    if "/catalog/item-" in catalog_url:
        return [product_from_fakel_card(manufacturer, catalog_url, soup)]

    products = collect_fakel_products_from_soup(manufacturer, catalog_url, soup, max_products)
    seen_product_urls = {product["url"] for product in products}

    category_urls = collect_fakel_category_urls(catalog_url, soup)
    for category_url in category_urls[:30]:
        if len(products) >= max_products:
            break
        try:
            response = requests.get(category_url, headers=HEADERS, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            continue

        category_soup = BeautifulSoup(response.text, "html.parser")
        found = collect_fakel_products_from_soup(
            manufacturer,
            category_url,
            category_soup,
            max_products - len(products),
        )
        for product in found:
            if product["url"] not in seen_product_urls:
                products.append(product)
                seen_product_urls.add(product["url"])

    return products


def looks_like_expert_product_url(url):
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    return (
        len(parts) >= 3
        and parts[0] == "catalog"
        and parts[1] == "spetsodezhda"
        and parts[-1] not in {"", "spetsodezhda"}
    )


def nearest_useful_text(tag):
    current = tag
    for _ in range(5):
        if current is None:
            break
        text = clean_text(current.get_text(" "))
        if extract_article(text) or extract_price(text):
            return text
        current = current.parent
    return clean_text(tag.get_text(" "))


def product_from_expert_card(manufacturer, url, soup):
    text = clean_text(soup.get_text(" "))
    title = soup.find("h1")
    name = clean_text(title.get_text(" ")) if title else ""
    article = extract_article(text)
    price = extract_price(text)
    stock = extract_stock(text)

    characteristics = []
    for label in [
        "Цвет",
        "Комплектация",
        "Коллекция",
        "Материал",
        "Размеры",
        "Рост",
    ]:
        value = extract_characteristic_value(text, label)
        if value:
            characteristics.append(f"{label}: {value}")

    description = clean_text(" ".join([name, *characteristics, text]))
    return product_from_text(manufacturer, name, description, url, article, price, stock)


def product_from_expert_catalog_row(manufacturer, url, name, row_text):
    description = clean_text(f"{name} {row_text}")
    return product_from_text(
        manufacturer=manufacturer,
        name=name,
        description=description,
        url=url,
        article=extract_article(row_text),
        price=extract_price(row_text),
        stock=extract_stock(row_text),
    )


def parse_expert_catalog(manufacturer, catalog_url, soup, max_products):
    if looks_like_expert_product_url(catalog_url):
        return [product_from_expert_card(manufacturer, catalog_url, soup)]

    products = []
    seen_urls = set()
    product_words = [
        "костюм",
        "куртка",
        "брюки",
        "полукомбинезон",
        "жилет",
        "халат",
        "фартук",
        "комбинезон",
    ]

    for link in soup.find_all("a", href=True):
        url = urljoin(catalog_url, link["href"])
        name = clean_text(link.get_text(" "))
        lowered_name = name.lower()

        if url in seen_urls or not looks_like_expert_product_url(url):
            continue
        if len(name) < 8 or not any(word in lowered_name for word in product_words):
            continue

        row_text = nearest_useful_text(link)
        products.append(product_from_expert_catalog_row(manufacturer, url, name, row_text))
        seen_urls.add(url)

        if len(products) >= max_products:
            break

    return products


def looks_like_spets_product_url(url):
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    return (
        len(parts) >= 4
        and parts[0] == "products"
        and not path.endswith("products")
        and not path.endswith("products/spetsodezhda")
    )


def looks_like_spets_category_url(url):
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    return (
        len(parts) >= 2
        and parts[0] == "products"
        and not looks_like_spets_product_url(url)
    )


def product_from_spets_card(manufacturer, url, soup):
    text = clean_text(soup.get_text(" "))
    title = soup.find("h1")
    name = clean_text(title.get_text(" ")) if title else ""
    article = extract_article(text)
    price = extract_price(text)
    stock = extract_stock(text)

    characteristics = []
    for label in [
        "Вид изделия",
        "Комплектность",
        "Назначение",
        "Основной цвет",
        "Состав",
        "Материал",
        "Утеплитель",
        "Климатические регионы",
        "Защитные свойства",
    ]:
        value = extract_characteristic_value(text, label)
        if value:
            characteristics.append(f"{label}: {value}")

    description = clean_text(" ".join([name, *characteristics, text]))
    return product_from_text(manufacturer, name, description, url, article, price, stock)


def product_from_spets_catalog_row(manufacturer, url, name, row_text):
    description = clean_text(f"{name} {row_text}")
    return product_from_text(
        manufacturer=manufacturer,
        name=name,
        description=description,
        url=url,
        article=extract_article(row_text),
        price=extract_price(row_text),
        stock=extract_stock(row_text),
    )


def collect_spets_products_from_soup(manufacturer, catalog_url, soup, max_products):
    products = []
    seen_urls = set()
    product_words = [
        "костюм",
        "куртка",
        "брюки",
        "полукомбинезон",
        "комбинезон",
        "жилет",
        "халат",
        "фартук",
        "рубашка",
        "футболка",
        "блуза",
    ]

    for link in soup.find_all("a", href=True):
        url = urljoin(catalog_url, link["href"])
        name = clean_text(link.get_text(" "))
        lowered_name = name.lower()

        if url in seen_urls or not looks_like_spets_product_url(url):
            continue
        if len(name) < 6 or not any(word in lowered_name for word in product_words):
            continue

        row_text = nearest_useful_text(link)
        products.append(product_from_spets_catalog_row(manufacturer, url, name, row_text))
        seen_urls.add(url)

        if len(products) >= max_products:
            break

    return products


def parse_spets_catalog(manufacturer, catalog_url, soup, max_products):
    if looks_like_spets_product_url(catalog_url):
        return [product_from_spets_card(manufacturer, catalog_url, soup)]

    products = collect_spets_products_from_soup(manufacturer, catalog_url, soup, max_products)
    if products:
        return products

    category_urls = []
    for link in soup.find_all("a", href=True):
        url = urljoin(catalog_url, link["href"])
        if url in category_urls:
            continue
        if looks_like_spets_category_url(url) and "/products/" in url:
            category_urls.append(url)

    for category_url in category_urls[:6]:
        if len(products) >= max_products:
            break
        try:
            response = requests.get(category_url, headers=HEADERS, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            continue

        category_soup = BeautifulSoup(response.text, "html.parser")
        products.extend(
            collect_spets_products_from_soup(
                manufacturer,
                category_url,
                category_soup,
                max_products - len(products),
            )
        )

    return products[:max_products]


def looks_like_product_block(tag):
    class_text = " ".join(tag.get("class", [])).lower()
    id_text = (tag.get("id") or "").lower()
    marker_text = f"{class_text} {id_text}"
    markers = ["product", "catalog", "card", "item", "goods", "tovar", "tile"]
    return any(marker in marker_text for marker in markers)


def parse_catalog(manufacturer, catalog_url, max_products=500):
    response = requests.get(catalog_url, headers=HEADERS, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    if urlparse(catalog_url).netloc.endswith("f-tk.ru"):
        return parse_fakel_catalog(manufacturer, catalog_url, soup, max_products)
    if urlparse(catalog_url).netloc.endswith("psk.expert"):
        return parse_expert_catalog(manufacturer, catalog_url, soup, max_products)
    if urlparse(catalog_url).netloc.endswith("spets.ru"):
        return parse_spets_catalog(manufacturer, catalog_url, soup, max_products)

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
