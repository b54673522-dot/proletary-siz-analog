from datetime import datetime

import streamlit as st

from data_store import (
    add_confirmed_analog,
    add_manufacturer,
    count_products,
    get_last_update,
    load_manufacturers,
    load_products,
    save_products,
)
from matcher import extract_characteristics, find_analogs
from site_parser import parse_catalog


st.set_page_config(page_title="Пролетарий: подбор аналогов СИЗ", layout="wide")


def format_value(value):
    if value in (None, "", []):
        return "не определено"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "не определено"
    return str(value)


def refresh_products():
    manufacturers = load_manufacturers()
    all_products = []
    errors = []

    for manufacturer in manufacturers:
        try:
            parsed = parse_catalog(
                manufacturer=manufacturer["manufacturer"],
                catalog_url=manufacturer["catalog_url"],
            )
            all_products.extend(parsed)
        except Exception as exc:
            errors.append(f"{manufacturer['manufacturer']}: {exc}")

    if all_products:
        save_products(all_products)

    return len(all_products), errors


st.title("Пролетарий: единая база СИЗ и подбор аналогов")
st.caption("Первая простая версия: сайты производителей -> база товаров -> позиция конкурента -> аналоги.")

if "auto_refresh_attempted" not in st.session_state:
    st.session_state.auto_refresh_attempted = False

if not st.session_state.auto_refresh_attempted and load_manufacturers() and not load_products():
    st.session_state.auto_refresh_attempted = True
    with st.spinner("Первый запуск: автоматически загружаю товары поставщиков..."):
        auto_count, auto_errors = refresh_products()
    if auto_count:
        st.success(f"Стартовая база товаров загружена. Собрано карточек: {auto_count}.")
    else:
        st.warning("Стартовую базу пока не удалось загрузить автоматически. Попробуйте нажать «Обновить товары».")
    for error in auto_errors:
        st.error(error)

st.header("База производителей")
st.info("Поставщики загружаются автоматически. Этот блок нужен только если вы хотите добавить новый сайт вручную.")

with st.form("manufacturer_form", clear_on_submit=False):
    col_name, col_url = st.columns([1, 2])
    with col_name:
        manufacturer_name = st.text_input("Производитель")
    with col_url:
        catalog_url = st.text_input("Ссылка на каталог производителя")

    submitted = st.form_submit_button("Добавить сайт")

if submitted:
    if not manufacturer_name.strip() or not catalog_url.strip():
        st.warning("Заполните производителя и ссылку на каталог.")
    else:
        add_manufacturer(manufacturer_name.strip(), catalog_url.strip())
        st.success("Сайт производителя добавлен.")

if st.button("Обновить товары", type="primary"):
    with st.spinner("Собираю товары с сайтов производителей..."):
        collected_count, parse_errors = refresh_products()

    if collected_count:
        st.success(f"Товары обновлены. Собрано карточек: {collected_count}.")
    else:
        st.warning("Не удалось собрать товары. Проверьте ссылки на каталоги.")

    for error in parse_errors:
        st.error(error)

manufacturers = load_manufacturers()
products = load_products()

metric_a, metric_b, metric_c = st.columns(3)
metric_a.metric("Производителей подключено", len(manufacturers))
metric_b.metric("Товаров собрано", count_products())
metric_c.metric("Дата последнего обновления", get_last_update() or "еще не было")

if manufacturers:
    with st.expander("Подключенные производители"):
        for item in manufacturers:
            st.write(f"**{item['manufacturer']}** - {item['catalog_url']}")

st.divider()

st.header("Позиция конкурента")
competitor_description = st.text_area("Описание товара конкурента", height=180)
competitor_url = st.text_input("Ссылка на товар конкурента", placeholder="Необязательно")

find_clicked = st.button("Подобрать аналог")

if find_clicked:
    if not competitor_description.strip():
        st.warning("Вставьте описание товара конкурента.")
        st.stop()

    extracted = extract_characteristics(competitor_description)
    analogs = find_analogs(competitor_description, products)

    st.header("Что определила система")
    char_rows = [
        ("категория", extracted.get("category")),
        ("подкатегория", extracted.get("subcategory")),
        ("тип товара", extracted.get("product_type")),
        ("сезон", extracted.get("season")),
        ("комплектация", extracted.get("kit")),
        ("состав ткани", extracted.get("composition")),
        ("название ткани", extracted.get("fabric_name")),
        ("плотность ткани", extracted.get("fabric_density")),
        ("защитные свойства", extracted.get("protective_properties")),
        ("СОП", extracted.get("sop")),
        ("цвет", extracted.get("color")),
        ("недостающие данные", extracted.get("missing_data")),
    ]

    st.table(
        [
            {"характеристика": label, "значение": format_value(value)}
            for label, value in char_rows
        ]
    )

    st.header("Подходящие СИЗ из ассортимента производителей")

    if not analogs:
        st.info("Пока нет подходящих товаров. Обновите базу товаров или добавьте больше производителей.")
    else:
        header = st.columns([1.2, 1, 1.4, 2.2, 1.2, 1, 2, 2, 2, 1.6, 1])
        header[0].markdown("**статус**")
        header[1].markdown("**совпадение, %**")
        header[2].markdown("**производитель**")
        header[3].markdown("**наш товар**")
        header[4].markdown("**артикул**")
        header[5].markdown("**цена**")
        header[6].markdown("**что совпало**")
        header[7].markdown("**что отличается**")
        header[8].markdown("**что уточнить**")
        header[9].markdown("**ссылка**")
        header[10].markdown("**выбор**")

        for index, analog in enumerate(analogs[:5], start=1):
            product = analog["product"]
            with st.container(border=True):
                cols = st.columns([1.2, 1, 1.4, 2.2, 1.2, 1, 2, 2, 2, 1.6, 1])
                cols[0].write(analog["status"])
                cols[1].write(f"{analog['score']}%")
                cols[2].write(product.get("manufacturer") or "")
                cols[3].write(product.get("name") or "")
                cols[4].write(product.get("article") or "")
                cols[5].write(product.get("price") or "")
                cols[6].write("; ".join(analog["matched"]) or "не найдено")
                cols[7].write("; ".join(analog["differences"]) or "нет")
                cols[8].write("; ".join(analog["to_clarify"]) or "нет")
                if product.get("url"):
                    cols[9].link_button("Карточка", product["url"])
                else:
                    cols[9].write("нет ссылки")

                if cols[10].button("Выбрать", key=f"select_{index}"):
                    add_confirmed_analog(
                        {
                            "competitor_position": competitor_description,
                            "competitor_url": competitor_url,
                            "manufacturer": product.get("manufacturer"),
                            "our_product": product.get("name"),
                            "article": product.get("article"),
                            "our_product_url": product.get("url"),
                            "match_percent": analog["score"],
                            "status": analog["status"],
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
                    st.success("Связка сохранена в data/confirmed_analogs.json")
