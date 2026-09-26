"""
Creates sales.csv - a small, clean, believable dataset to test the agent on.
Run this once:  python make_data.py
"""

import csv
import random
from datetime import date, timedelta

random.seed(42)  # same data every time you run it, which makes debugging sane

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["Basic Plan", "Pro Plan", "Enterprise Plan", "Add-on Storage"]
CHANNELS = ["Direct", "Partner", "Online"]

# roughly what each product costs, so revenue isn't random noise
PRICES = {
    "Basic Plan": 29,
    "Pro Plan": 99,
    "Enterprise Plan": 499,
    "Add-on Storage": 15,
}

START = date(2024, 1, 1)
ROWS = 600

rows = []
for i in range(ROWS):
    day = START + timedelta(days=random.randint(0, 545))
    product = random.choices(PRODUCTS, weights=[40, 30, 10, 20])[0]
    units = random.randint(1, 6)
    region = random.choice(REGIONS)

    # give the West region a slump in 2025 so there's something real to find
    price = PRICES[product]
    if region == "West" and day.year == 2025:
        units = max(1, units - 2)

    rows.append({
        "order_id": 10000 + i,
        "order_date": day.isoformat(),
        "region": region,
        "product": product,
        "channel": random.choice(CHANNELS),
        "units": units,
        "revenue": round(units * price, 2),
        "customer_id": f"C{random.randint(1, 180):04d}",
    })

rows.sort(key=lambda r: r["order_date"])

with open("sales.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote sales.csv with {len(rows)} rows.")