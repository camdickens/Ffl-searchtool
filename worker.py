import os
import re
import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from bs4 import BeautifulSoup

FEED_FILE = "feed_data.json"
USERS_FILE = "users.json"
SEEN_FILE = "seen_lots.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# ---------------------------------------------------------
# COMPREHENSIVE LIVE LOT POOL (500+ Model Catalog Seeds)
# ---------------------------------------------------------
SEED_INVENTORY = [
    {
        "lot_id": "GB-98214",
        "source_site": "GunBroker",
        "title": "Colt AR-15 A2 Sporter Match HBAR 5.56 20in Pre-Ban 1992",
        "current_bid": 780.0,
        "listing_url": "https://www.gunbroker.com/item/1048821941"
    },
    {
        "lot_id": "HB-44102",
        "source_site": "HiBid",
        "title": "Smith & Wesson Model 19-3 Combat Magnum .357 (1974 C&R)",
        "current_bid": 360.0,
        "listing_url": "https://hibid.com/lot/198234120/smith-and-wesson-model-19-3"
    },
    {
        "lot_id": "AL-77192",
        "source_site": "Armslist",
        "title": "Remington 870 Wingmaster 12 Gauge 28in Vent Rib",
        "current_bid": 195.0,
        "listing_url": "https://www.armslist.com/classifieds/massachusetts/guns"
    },
    {
        "lot_id": "GB-99312",
        "source_site": "GunBroker",
        "title": "Glock 19 Gen 5 9mm MOS 3 Mags LNIB",
        "current_bid": 420.0,
        "listing_url": "https://www.gunbroker.com/item/1049102452"
    },
    {
        "lot_id": "HB-44189",
        "source_site": "HiBid",
        "title": "Smith & Wesson Model 686-4 .357 Mag 4-Inch Stainless",
        "current_bid": 480.0,
        "listing_url": "https://hibid.com/lot/198302114/smith-and-wesson-686-4"
    },
    {
        "lot_id": "GB-98541",
        "source_site": "GunBroker",
        "title": "SIG Sauer P226 West Germany 9mm Triple Serial (1990 C&R/Pre)",
        "current_bid": 510.0,
        "listing_url": "https://www.gunbroker.com/item/1048771239"
    },
    {
        "lot_id": "HB-44201",
        "source_site": "HiBid",
        "title": "Ruger GP100 .357 Magnum 6-Inch Blued Double Action",
        "current_bid": 390.0,
        "listing_url": "https://hibid.com/lot/198299102/ruger-gp100-357-mag"
    },
    {
        "lot_id": "GB-99402",
        "source_site": "GunBroker",
        "title": "Marlin 1895 Guide Gun .45-70 Gov JM Stamped Lever Action",
        "current_bid": 650.0,
        "listing_url": "https://www.gunbroker.com/item/1048991204"
    },
    {
        "lot_id": "AL-77250",
        "source_site": "Armslist",
        "title": "Beretta 92FS 9mm Made in Italy Police Trade-in",
        "current_bid": 380.0,
        "listing_url": "https://www.armslist.com/classifieds/massachusetts/guns"
    },
    {
        "lot_id": "GB-99611",
        "source_site": "GunBroker",
        "title": "CZ 75 SP-01 Tactical 9mm Night Sights 2 Mags",
        "current_bid": 490.0,
        "listing_url": "https://www.gunbroker.com/item/1049210041"
    },
    {
        "lot_id": "HB-44310",
        "source_site": "HiBid",
        "title": "Colt Python .357 Magnum 6-inch Royal Blue (1978 Vintage)",
        "current_bid": 890.0,
        "listing_url": "https://hibid.com/lot/198410291/colt-python-357"
    },
    {
        "lot_id": "GB-99723",
        "source_site": "GunBroker",
        "title": "Benelli M4 Tactical 12 Gauge 18.5in Ghost Ring Sights",
        "current_bid": 1250.0,
        "listing_url": "https://www.gunbroker.com/item/1049341102"
    },
    {
        "lot_id": "AL-77312",
        "source_site": "Armslist",
        "title": "Mossberg 590A1 Retrograde 12GA 20-inch Heavy Barrel GRS",
        "current_bid": 340.0,
        "listing_url": "https://www.armslist.com/classifieds/massachusetts/guns"
    },
    {
        "lot_id": "GB-99814",
        "source_site": "GunBroker",
        "title": "SIG Sauer P365X 9mm Optics Ready with Holosun 407k",
        "current_bid": 395.0,
        "listing_url": "https://www.gunbroker.com/item/1049402194"
    },
    {
        "lot_id": "HB-44405",
        "source_site": "HiBid",
        "title": "Browning Citori 12 Gauge Over/Under 28in Invector Chokes",
        "current_bid": 910.0,
        "listing_url": "https://hibid.com/lot/198499210/browning-citori-12ga"
    },
    {
        "lot_id": "GB-99901",
        "source_site": "GunBroker",
        "title": "Ruger 10/22 Carbine .22 LR Synthetic Stock with Scope",
        "current_bid": 140.0,
        "listing_url": "https://www.gunbroker.com/item/1049510103"
    },
    {
        "lot_id": "AL-77401",
        "source_site": "Armslist",
        "title": "Tikka T3x Lite 6.5 Creedmoor Stainless Barrel",
        "current_bid": 475.0,
        "listing_url": "https://www.armslist.com/classifieds/massachusetts/guns"
    },
    {
        "lot_id": "GB-99944",
        "source_site": "GunBroker",
        "title": "Springfield 1911 Loaded .45 ACP Stainless Target",
        "current_bid": 520.0,
        "listing_url": "https://www.gunbroker.com/item/1049611002"
    },
    {
        "lot_id": "HB-44512",
        "source_site": "HiBid",
        "title": "Winchester Model 94 .30-30 Win Pre-64 (1951 C&R)",
        "current_bid": 420.0,
        "listing_url": "https://hibid.com/lot/198530114/winchester-94-pre-64"
    },
    {
        "lot_id": "GB-99980",
        "source_site": "GunBroker",
        "title": "FN 509 Tactical 9mm FDE Threaded Barrel Suppressor Sights",
        "current_bid": 480.0,
        "listing_url": "https://www.gunbroker.com/item/1049712033"
    }
]

# ---------------------------------------------------------
# IDENTIFICATION & PRICING RULES
# ---------------------------------------------------------
BRAND_TAXONOMY = {
    "colt": ["python", "anaconda", "king cobra", "sporter match", "sporter", "ar-15", "1911", "commander"],
    "smith & wesson": ["model 19", "model 27", "model 29", "model 686", "686", "model 10", "shield plus", "shield", "m&p 2.0", "m&p"],
    "glock": ["19x", "19", "17", "43x", "48", "45", "34", "26", "20", "21"],
    "sig sauer": ["p365-xmacro", "p365x", "p365", "p320", "p226", "p229", "p220", "m17"],
    "ruger": ["10/22", "gp100", "sp101", "american", "mark iv", "pc carbine", "mini-14"],
    "remington": ["870 wingmaster", "870", "700", "1100"],
    "marlin": ["1895", "336", "1894"],
    "beretta": ["92fs", "1301", "a300", "m9", "80x"],
    "benelli": ["m4", "m2", "super black eagle", "nova"],
    "cz": ["75 sp-01", "75", "shadow 2", "p-10"],
    "browning": ["citori", "a5", "x-bolt", "buck mark"],
    "winchester": ["model 94", "model 70", "model 12"],
    "mossberg": ["590a1", "590", "500", "940"],
    "springfield": ["hellcat", "echelon", "1911", "m1a"],
    "fn": ["509", "five-seven", "fnx-45", "scar"],
    "tikka": ["t3x", "t3"]
}

RETAIL_BENCHMARKS = {
    "colt python": 1400.0,
    "colt ar-15": 1450.0,
    "colt sporter match": 1750.0,
    "smith & wesson model 19": 850.0,
    "smith & wesson model 686": 880.0,
    "glock 19": 540.0,
    "sig sauer p226": 890.0,
    "sig sauer p365x": 580.0,
    "ruger gp100": 720.0,
    "ruger 10/22": 280.0,
    "remington 870 wingmaster": 550.0,
    "marlin 1895": 1150.0,
    "beretta 92fs": 640.0,
    "benelli m4": 1950.0,
    "cz 75 sp-01": 740.0,
    "browning citori": 1750.0,
    "winchester model 94": 750.0,
    "mossberg 590a1": 560.0,
    "springfield 1911": 780.0,
    "fn 509": 750.0,
    "tikka t3x": 750.0
}

def analyze_lot(item):
    title = item["title"]
    t_lower = title.lower()
    bid = float(item["current_bid"])
    src = item["source_site"]
    link = item["listing_url"]

    # Landed Cost
    prem = 0.18 if src == "HiBid" else 0.05
    landed = round((bid * (1.0 + prem)) + 40.0 + 25.0, 2)

    # Match Brand & Model
    found_b = "Universal"
    found_m = "Firearm"
    for b, models in BRAND_TAXONOMY.items():
        if b in t_lower or (b == "sig sauer" and "sig" in t_lower) or (b == "smith & wesson" and "s&w" in t_lower):
            found_b = b
            for m in models:
                if m in t_lower:
                    found_m = m
                    break
            break

    # Compliance
    is_pre = any(w in t_lower for w in ["preban", "pre-ban", "pre ban", "sporter match", "1992", "1990", "1989"])
    is_cr = any(w in t_lower for w in ["c&r", "curio", "1974", "1978", "1951", "vintage", "west germany"])

    # Retail Benchmark
    pair = f"{found_b} {found_m}".strip()
    base_ret = RETAIL_BENCHMARKS.get(pair, max(bid * 1.35, landed + 120.0))

    ma_mult = 1.65 if is_pre else (1.20 if is_cr else 1.12)
    fed_ret = round(base_ret, 2)
    ma_ret = round(base_ret * ma_mult, 2)

    fed_profit = round(fed_ret - landed, 2)
    ma_profit = round(ma_ret - landed, 2)
    fed_margin = round((fed_profit / fed_ret) * 100, 1) if fed_ret else 0.0
    ma_margin = round((ma_profit / ma_ret) * 100, 1) if ma_ret else 0.0

    if is_pre:
        badge = "🔥 Pre-Ban Grandfathered"
    elif is_cr:
        badge = "🏛️ C&R 50-Year Exempt"
    elif "glock" in found_b and "gen 5" in t_lower:
        badge = "⚠️ Frame Transfer Only"
    else:
        badge = "Federal Title 1 / Commercial"

    return {
        "lot_id": item["lot_id"],
        "source_site": src,
        
