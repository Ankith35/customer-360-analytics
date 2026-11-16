"""
02_data_cleaning.py
Reads raw Olist CSVs, applies the cleaning rules found during profiling,
and writes cleaned files to data/processed/.
Raw files are never modified.
"""
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW_DIR = BASE / "data" / "raw"
OUT_DIR = BASE / "data" / "processed"
OUT_DIR.mkdir(exist_ok=True)


def load(name):
    return pd.read_csv(RAW_DIR / name)


customers = load("olist_customers_dataset.csv")
orders = load("olist_orders_dataset.csv")
items = load("olist_order_items_dataset.csv")
payments = load("olist_order_payments_dataset.csv")
reviews = load("olist_order_reviews_dataset.csv")
products = load("olist_products_dataset.csv")
geo = load("olist_geolocation_dataset.csv")
translation = load("product_category_name_translation.csv")

# ---------------------------------------------------------------
# Part 2: dates and delivery metrics (rules 1 and 2)
# ---------------------------------------------------------------
date_cols = [
    "order_purchase_timestamp", "order_approved_at",
    "order_delivered_carrier_date", "order_delivered_customer_date",
    "order_estimated_delivery_date",
]
for col in date_cols:
    orders[col] = pd.to_datetime(orders[col])

orders["is_delivered"] = orders["order_status"] == "delivered"

# Delivery metrics only for delivered orders that actually have a delivery date
valid_delivery = orders["is_delivered"] & orders["order_delivered_customer_date"].notna()

orders["delivery_days"] = (
    (orders["order_delivered_customer_date"] - orders["order_purchase_timestamp"])
    .dt.total_seconds() / 86400
).where(valid_delivery)

orders["is_late"] = (
    (orders["order_delivered_customer_date"] > orders["order_estimated_delivery_date"])
    .astype("boolean")
    .where(valid_delivery)
)

# ---------------------------------------------------------------
# Part 3: one row per order for items, payments, reviews
# ---------------------------------------------------------------
items_agg = items.groupby("order_id").agg(
    item_count=("order_item_id", "count"),
    items_revenue=("price", "sum"),
    freight_total=("freight_value", "sum"),
    distinct_products=("product_id", "nunique"),
    distinct_sellers=("seller_id", "nunique"),
).reset_index()

# Zero-value payment rows (the 3 'not_defined') carry no information
payments_nz = payments[payments["payment_value"] > 0]

payments_agg = payments_nz.groupby("order_id").agg(
    payment_total=("payment_value", "sum"),
    payment_rows=("payment_sequential", "count"),
    max_installments=("payment_installments", "max"),
).reset_index()

main_type = (
    payments_nz.sort_values("payment_value", ascending=False)
    .drop_duplicates("order_id")[["order_id", "payment_type"]]
    .rename(columns={"payment_type": "main_payment_type"})
)
payments_agg = payments_agg.merge(main_type, on="order_id")

# Reviews: keep only the most recent review per order
reviews["review_answer_timestamp"] = pd.to_datetime(reviews["review_answer_timestamp"])
latest_review = (
    reviews.sort_values(["order_id", "review_answer_timestamp"])
    .drop_duplicates("order_id", keep="last")
    [["order_id", "review_id", "review_score"]]
)

# ---------------------------------------------------------------
# Part 4: order-level table, with a safety check
# ---------------------------------------------------------------
order_summary = (
    orders
    .merge(customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left")
    .merge(items_agg, on="order_id", how="left")
    .merge(payments_agg, on="order_id", how="left")
    .merge(latest_review, on="order_id", how="left")
)

assert len(order_summary) == len(orders), "Join changed the row count!"

# ---------------------------------------------------------------
# Part 5: products and geolocation
# ---------------------------------------------------------------
extra_translations = pd.DataFrame({
    "product_category_name": ["pc_gamer", "portateis_cozinha_e_preparadores_de_alimentos"],
    "product_category_name_english": ["pc_gamer", "portable_kitchen_food_preparers"],
})
translation_full = pd.concat([translation, extra_translations], ignore_index=True)

products_clean = (
    products
    .rename(columns={
        "product_name_lenght": "product_name_length",
        "product_description_lenght": "product_description_length",
    })
    .merge(translation_full, on="product_category_name", how="left")
)
products_clean["product_category_name_english"] = (
    products_clean["product_category_name_english"].fillna("unknown")
)
assert len(products_clean) == len(products), "Product join changed the row count!"

geo_clean = (
    geo.drop_duplicates()
    .groupby("geolocation_zip_code_prefix")
    .agg(
        avg_lat=("geolocation_lat", "mean"),
        avg_lng=("geolocation_lng", "mean"),
        city=("geolocation_city", "first"),
        state=("geolocation_state", "first"),
    )
    .reset_index()
)

# ---------------------------------------------------------------
# Part 6: save results and print a quality report
# ---------------------------------------------------------------
order_summary.to_csv(OUT_DIR / "orders_clean.csv", index=False)
products_clean.to_csv(OUT_DIR / "products_clean.csv", index=False)
geo_clean.to_csv(OUT_DIR / "geolocation_clean.csv", index=False)

print("=== CLEANING REPORT ===")
print(f"orders_clean rows:         {len(order_summary):,}")
print(f"products_clean rows:       {len(products_clean):,}")
print(f"geolocation_clean rows:    {len(geo_clean):,}")
print(f"Delivered orders:          {order_summary['is_delivered'].sum():,}")
print(f"Excluded from delivery metrics (delivered, no date): "
      f"{(order_summary['is_delivered'] & order_summary['order_delivered_customer_date'].isna()).sum()}")
print(f"Orders with no review:     {order_summary['review_score'].isna().sum():,}")
print(f"Products labelled unknown: {(products_clean['product_category_name_english'] == 'unknown').sum():,}")
print(f"Delivered revenue (items): R${order_summary.loc[order_summary['is_delivered'], 'items_revenue'].sum():,.2f}")