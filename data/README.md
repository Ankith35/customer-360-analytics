# Data

## Source
Core transactional data comes from the **Olist Brazilian E-commerce Public Dataset** (Kaggle) : ~100K orders from  2016-2018 across customers, orders, items, payments,reviews, products and sellers.

## Not included in this repo
Raw CSVs are excluded via .gitignore. To reproduce:
1. Download the dataset from Kaggle
2. Extract the 9 CSVs into `data/raw/`

## Synthetic data
Support tickets, marketing events, website events and enagagement data are synthetically generated with python(Faker) to demonstrate enterprise Customer 360 analytics. Generate scripts are in `/python`.
