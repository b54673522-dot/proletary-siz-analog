import json
from datetime import datetime
from pathlib import Path


DATA_DIR = Path("data")
PRODUCTS_FILE = DATA_DIR / "products_cache.json"
CONFIRMED_FILE = DATA_DIR / "confirmed_analogs.json"
MANUFACTURERS_FILE = DATA_DIR / "manufacturers.json"

DEFAULT_MANUFACTURERS = [
    {
        "manufacturer": "Факел",
        "catalog_url": "https://www.f-tk.ru/catalog/spetsodezhda/",
        "added_at": "default",
    }
]


def ensure_data_files():
    DATA_DIR.mkdir(exist_ok=True)
    for path in (PRODUCTS_FILE, CONFIRMED_FILE, MANUFACTURERS_FILE):
        if not path.exists():
            path.write_text("[]", encoding="utf-8")


def read_json(path):
    ensure_data_files()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def write_json(path, data):
    ensure_data_files()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_products():
    return read_json(PRODUCTS_FILE)


def save_products(products):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized = []
    for product in products:
        item = normalize_product(product)
        item["updated_at"] = now
        normalized.append(item)
    write_json(PRODUCTS_FILE, normalized)


def count_products():
    return len(load_products())


def get_last_update():
    products = load_products()
    dates = [item.get("updated_at") for item in products if item.get("updated_at")]
    return max(dates) if dates else None


def load_manufacturers():
    manufacturers = read_json(MANUFACTURERS_FILE)
    if not manufacturers:
        write_json(MANUFACTURERS_FILE, DEFAULT_MANUFACTURERS)
        return DEFAULT_MANUFACTURERS

    changed = False
    for default_item in DEFAULT_MANUFACTURERS:
        existing = next(
            (
                item
                for item in manufacturers
                if item.get("manufacturer", "").lower()
                == default_item["manufacturer"].lower()
            ),
            None,
        )
        if existing:
            if existing.get("catalog_url") != default_item["catalog_url"]:
                existing["catalog_url"] = default_item["catalog_url"]
                existing["added_at"] = existing.get("added_at") or "default"
                changed = True
        else:
            manufacturers.append(default_item)
            changed = True

    if changed:
        write_json(MANUFACTURERS_FILE, manufacturers)
    return manufacturers


def add_manufacturer(manufacturer, catalog_url):
    manufacturers = load_manufacturers()
    normalized_url = catalog_url.strip()
    normalized_name = manufacturer.strip()

    for item in manufacturers:
        if item["manufacturer"].lower() == normalized_name.lower():
            item["catalog_url"] = normalized_url
            write_json(MANUFACTURERS_FILE, manufacturers)
            return

    manufacturers.append(
        {
            "manufacturer": normalized_name,
            "catalog_url": normalized_url,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    write_json(MANUFACTURERS_FILE, manufacturers)


def add_confirmed_analog(analog):
    confirmed = read_json(CONFIRMED_FILE)
    confirmed.append(analog)
    write_json(CONFIRMED_FILE, confirmed)


def normalize_product(product):
    fields = [
        "manufacturer",
        "name",
        "article",
        "category",
        "subcategory",
        "product_type",
        "season",
        "composition",
        "fabric_name",
        "fabric_density",
        "protective_properties",
        "sop",
        "color",
        "description",
        "price",
        "stock",
        "url",
    ]
    return {field: product.get(field, "") for field in fields}
