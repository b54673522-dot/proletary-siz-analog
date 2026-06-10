import re


PRODUCT_FIELDS = [
    "category",
    "subcategory",
    "product_type",
    "season",
    "kit",
    "composition",
    "fabric_name",
    "fabric_density",
    "protective_properties",
    "sop",
    "color",
]


def normalize_text(text):
    return (text or "").lower().replace("ё", "е")


def contains_any(text, words):
    return any(word in text for word in words)


def extract_density(text):
    match = re.search(r"(\d{2,3})\s*(?:г/м2|г/м²|гр/м2|гр/м²|г\s*/\s*м)", text)
    if match:
        return int(match.group(1))
    return None


def extract_characteristics(text):
    source = normalize_text(text)
    result = {field: "" for field in PRODUCT_FIELDS}

    if contains_any(source, ["ботинки", "полуботинки", "сапоги", "кроссовки"]):
        result["category"] = "спецобувь"
    elif contains_any(source, ["перчатки", "рукавицы", "краги"]):
        result["category"] = "защита рук"
    elif contains_any(source, ["респиратор", "полумаска", "фильтр", "сизод", "маска"]):
        result["category"] = "СИЗОД"
    elif contains_any(source, ["костюм", "куртка", "брюки", "полукомбинезон", "халат", "жилет"]):
        result["category"] = "спецодежда"

    if contains_any(source, ["летний", "летняя", "лето"]):
        result["season"] = "лето"
        if result["category"] == "спецодежда":
            result["subcategory"] = "летняя спецодежда"
    elif contains_any(source, ["зимний", "зимняя", "утепленный", "утепленная", "зима"]):
        result["season"] = "зима"
        if result["category"] == "спецодежда":
            result["subcategory"] = "зимняя спецодежда"
    elif contains_any(source, ["демисезон", "всесезон"]):
        result["season"] = "демисезон"

    type_words = [
        "костюм",
        "куртка",
        "брюки",
        "полукомбинезон",
        "ботинки",
        "полуботинки",
        "сапоги",
        "кроссовки",
        "перчатки",
        "рукавицы",
        "краги",
        "респиратор",
        "полумаска",
        "фильтр",
        "жилет",
        "халат",
    ]
    for word in type_words:
        if word in source:
            result["product_type"] = word
            break

    kit = []
    for word in ["куртка", "брюки", "полукомбинезон", "жилет"]:
        if word in source:
            kit.append(word)
    result["kit"] = kit

    compositions = []
    for word in ["хлопок", "полиэфир", "смесовая", "полиэстер", "нейлон", "кожа", "спилок"]:
        if word in source:
            compositions.append(word)
    result["composition"] = ", ".join(compositions)

    for fabric in ["грета", "саржа", "твил", "оксфорд", "молескин", "брезент", "рип-стоп"]:
        if fabric in source:
            result["fabric_name"] = fabric
            break

    result["fabric_density"] = extract_density(source)

    properties = []
    property_map = {
        "диэлектр": "диэлектрические свойства",
        "сварщик": "сварочные работы",
        "сварочный": "сварочные работы",
        "огнестой": "огнестойкость",
        "кислот": "защита от кислот",
        "щелоч": "защита от щелочей",
        "нефт": "защита от нефти",
        "масл": "защита от масел",
        "влага": "влагозащита",
        "водо": "влагозащита",
        "антистат": "антистатические свойства",
        "мороз": "защита от холода",
    }
    for marker, label in property_map.items():
        if marker in source and label not in properties:
            properties.append(label)
    result["protective_properties"] = properties

    if contains_any(source, ["соп", "светоотраж", "световозвращ"]):
        result["sop"] = "есть"

    colors = [
        "черный",
        "синий",
        "серый",
        "красный",
        "оранжевый",
        "желтый",
        "зеленый",
        "белый",
        "васильковый",
        "темно-синий",
    ]
    for color in colors:
        if color in source:
            result["color"] = color
            break

    missing = []
    for field in PRODUCT_FIELDS:
        if not result.get(field):
            missing.append(field)
    result["missing_data"] = missing
    return result


def product_text(product):
    parts = [
        product.get("name"),
        product.get("category"),
        product.get("subcategory"),
        product.get("product_type"),
        product.get("season"),
        product.get("composition"),
        product.get("fabric_name"),
        str(product.get("fabric_density") or ""),
        " ".join(product.get("protective_properties", []))
        if isinstance(product.get("protective_properties"), list)
        else product.get("protective_properties"),
        product.get("sop"),
        product.get("color"),
        product.get("description"),
    ]
    return " ".join(part for part in parts if part)


def density_is_close(first, second):
    if not first or not second:
        return False
    try:
        first_num = float(first)
        second_num = float(second)
    except (TypeError, ValueError):
        return False
    if first_num == 0 or second_num == 0:
        return False
    difference = abs(first_num - second_num) / max(first_num, second_num)
    return difference <= 0.2


def values_overlap(first, second):
    if not first or not second:
        return False
    if isinstance(first, list):
        first_values = {normalize_text(item) for item in first}
    else:
        first_values = {item.strip() for item in normalize_text(str(first)).split(",") if item.strip()}
    if isinstance(second, list):
        second_values = {normalize_text(item) for item in second}
    else:
        second_values = {item.strip() for item in normalize_text(str(second)).split(",") if item.strip()}
    return bool(first_values & second_values)


def violates_hard_rules(competitor, product_chars):
    comp_type = competitor.get("product_type")
    comp_category = competitor.get("category")
    comp_season = competitor.get("season")
    product_category = product_chars.get("category")
    product_season = product_chars.get("season")

    if comp_type == "костюм" and comp_season in ("лето", "зима"):
        if product_category != "спецодежда" or product_season != comp_season:
            return True
    if comp_category in ("спецобувь", "защита рук", "СИЗОД") and product_category != comp_category:
        return True
    if values_overlap(competitor.get("protective_properties"), ["диэлектрические свойства"]):
        if not values_overlap(product_chars.get("protective_properties"), ["диэлектрические свойства"]):
            return True
    if values_overlap(competitor.get("protective_properties"), ["сварочные работы"]):
        if not values_overlap(product_chars.get("protective_properties"), ["сварочные работы"]) and product_chars.get("product_type") != "краги":
            return True
    return False


def score_product(competitor_chars, product):
    product_chars = extract_characteristics(product_text(product))
    matched = []
    differences = []
    to_clarify = []
    score = 0

    if violates_hard_rules(competitor_chars, product_chars):
        return {
            "score": 0,
            "status": "Не предлагать",
            "matched": [],
            "differences": ["не проходит жесткие правила подбора"],
            "to_clarify": [],
            "product": product,
        }

    checks = [
        ("subcategory", "подкатегория", 20),
        ("product_type", "тип товара", 15),
        ("season", "сезон", 15),
        ("protective_properties", "защитные свойства", 20),
        ("kit", "комплектация", 10),
        ("composition", "состав ткани", 8),
        ("color", "цвет", 0),
    ]

    for field, label, points in checks:
        comp_value = competitor_chars.get(field)
        product_value = product_chars.get(field)
        if not comp_value or not product_value:
            if points:
                to_clarify.append(label)
        elif values_overlap(comp_value, product_value) or comp_value == product_value:
            score += points
            matched.append(label)
        elif points:
            differences.append(label)

    if density_is_close(competitor_chars.get("fabric_density"), product_chars.get("fabric_density")):
        score += 7
        matched.append("плотность ткани")
    elif competitor_chars.get("fabric_density") and product_chars.get("fabric_density"):
        differences.append("плотность ткани")
    else:
        to_clarify.append("плотность ткани")

    if product.get("price") or product.get("stock"):
        score += 5
        matched.append("цена / наличие")
    else:
        to_clarify.append("цена / наличие")

    protective_match = values_overlap(
        competitor_chars.get("protective_properties"),
        product_chars.get("protective_properties"),
    )
    enough_data = len(to_clarify) <= 3

    if score >= 85 and protective_match:
        status = "Сильный аналог"
    elif score >= 65:
        status = "Близкий аналог"
    elif score >= 45:
        status = "Требует уточнения"
    else:
        status = "Не предлагать"

    if competitor_chars.get("protective_properties") and not protective_match and status == "Сильный аналог":
        status = "Близкий аналог"
    if not enough_data and status in ("Сильный аналог", "Близкий аналог"):
        status = "Требует уточнения"

    return {
        "score": min(score, 100),
        "status": status,
        "matched": matched,
        "differences": differences,
        "to_clarify": to_clarify,
        "product": product,
    }


def find_analogs(competitor_description, products, limit=5):
    competitor_chars = extract_characteristics(competitor_description)
    scored = [score_product(competitor_chars, product) for product in products]
    filtered = [item for item in scored if item["status"] != "Не предлагать"]
    filtered.sort(key=lambda item: item["score"], reverse=True)
    return filtered[:limit]
