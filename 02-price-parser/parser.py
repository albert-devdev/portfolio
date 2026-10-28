"""Мониторинг цен конкурентов: парсер каталога + история цен + Excel-отчёт + уведомления.

Демонстрация на books.toscrape.com — учебном сайте, созданном специально для парсинга.
Каждый запуск:
  1. параллельно обходит все категории и страницы каталога;
  2. сравнивает цены с прошлым запуском (история хранится в SQLite);
  3. строит Excel-отчёт: сводка с графиком, все товары, изменения цен;
  4. по желанию присылает список изменений в Telegram.

Запуск:
  python parser.py                       # весь каталог (~1000 товаров)
  python parser.py --categories 5        # быстрая проверка на 5 категориях
  python parser.py --notify              # + уведомление в Telegram (BOT_TOKEN и CHAT_ID в .env)
  python parser.py --simulate-changes 15 # ДЕМО: имитирует изменение 15 цен, чтобы показать отчёт
"""
import argparse
import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import history
import report

START_URL = "https://books.toscrape.com/index.html"
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
HEADERS = {"User-Agent": "Mozilla/5.0 (portfolio price monitor demo)"}

log = logging.getLogger("parser")
_local = threading.local()


def session():
    """Отдельная сессия на каждый поток: requests.Session не потокобезопасна."""
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers.update(HEADERS)
    return _local.s


def fetch(url, retries=3, delay=0.2):
    for attempt in range(retries):
        try:
            r = session().get(url, timeout=15)
            r.raise_for_status()
            r.encoding = "utf-8"
            time.sleep(delay)  # бережём сайт
            return BeautifulSoup(r.text, "html.parser")
        except requests.RequestException as e:
            if attempt == retries - 1:
                raise
            log.warning("Повтор %s (%s)", url, e)
            time.sleep(2 ** attempt)


def get_categories():
    soup = fetch(START_URL)
    return [
        (a.text.strip(), urljoin(START_URL, a["href"]))
        for a in soup.select("div.side_categories ul li ul li a")
    ]


def parse_cards(soup, page_url, category):
    items = []
    for card in soup.select("article.product_pod"):
        link = card.h3.a
        items.append({
            "title": link["title"],
            "category": category,
            "price": float(card.select_one(".price_color").text.replace("£", "").replace("Â", "")),
            "rating": RATINGS.get(card.select_one(".star-rating")["class"][1], 0),
            "in_stock": "In stock" in card.select_one(".availability").text,
            "url": urljoin(page_url, link["href"]),
        })
    return items


def scrape_category(name, url):
    """Проходит все страницы категории по кнопке «next»."""
    items = []
    while url:
        soup = fetch(url)
        items.extend(parse_cards(soup, url, name))
        nxt = soup.select_one("li.next a")
        url = urljoin(url, nxt["href"]) if nxt else None
    return items


def scrape(limit=None, workers=6):
    categories = get_categories()[:limit] if limit else get_categories()
    items = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(scrape_category, n, u): n for n, u in categories}
        for i, f in enumerate(as_completed(futures), 1):
            got = f.result()
            items.extend(got)
            log.info("[%d/%d] %s — %d шт.", i, len(categories), futures[f], len(got))
    return items


def find_changes(items, previous):
    changes = []
    for it in items:
        old = previous.get(it["url"])
        if old is not None and abs(old - it["price"]) >= 0.01:
            changes.append({**it, "old_price": old, "diff": round(it["price"] - old, 2)})
    return sorted(changes, key=lambda c: c["diff"] / c["old_price"])


def simulate(previous, items, n):
    """ДЕМО-режим: на учебном сайте цены не меняются, поэтому «сдвигаем» прошлые цены у n товаров."""
    for it in random.sample(items, min(n, len(items))):
        previous[it["url"]] = round(it["price"] * random.uniform(0.75, 1.3), 2)


def notify(changes, total):
    token, chat = os.getenv("BOT_TOKEN"), os.getenv("CHAT_ID")
    if not (token and chat):
        log.warning("Для --notify укажите BOT_TOKEN и CHAT_ID в .env")
        return
    lines = [f"📊 Мониторинг цен: {total} товаров, изменений: {len(changes)}"]
    for c in changes[:15]:
        arrow = "🔻" if c["diff"] < 0 else "🔺"
        lines.append(f"{arrow} {c['title'][:40]}: £{c['old_price']:.2f} → £{c['price']:.2f}")
    if len(changes) > 15:
        lines.append(f"…и ещё {len(changes) - 15} в отчёте")
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                  data={"chat_id": chat, "text": "\n".join(lines)}, timeout=15)


def main():
    ap = argparse.ArgumentParser(description="Мониторинг цен каталога")
    ap.add_argument("--categories", type=int, help="ограничить число категорий (для быстрой проверки)")
    ap.add_argument("--workers", type=int, default=6, help="параллельных потоков")
    ap.add_argument("--out", default=f"report_{datetime.now():%Y-%m-%d}.xlsx", help="файл отчёта")
    ap.add_argument("--notify", action="store_true", help="прислать изменения в Telegram")
    ap.add_argument("--simulate-changes", type=int, default=0, metavar="N", help="ДЕМО: имитировать N изменений")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    started = time.time()
    items = scrape(args.categories, args.workers)
    previous = history.last_prices()
    if args.simulate_changes:
        simulate(previous, items, args.simulate_changes)
    changes = find_changes(items, previous)
    history.save(items)

    report.build(items, changes, args.out, demo=bool(args.simulate_changes))
    log.info("Готово за %.0f сек: %d товаров, %d изменений цен → %s",
             time.time() - started, len(items), len(changes), args.out)
    if args.notify:
        notify(changes, len(items))


if __name__ == "__main__":
    main()
