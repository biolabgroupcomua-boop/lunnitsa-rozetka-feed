# -*- coding: utf-8 -*-
"""Довідник meloni.json для фіду Meloni (16.11.2026): 25 товарів MLN… з файлу Інесси Бібіної «Перелік_товарів_для_знижки_в_Розетка.xlsx»
(вивантаження кабінету Розетки, ключ — «ID з прайсу продавця») + фото й поточна ціна з картки rozetka.com.ua.
Pricecreator з повторного імпорту бере лише ціну, стару ціну, наявність і кількість (p371), тож назви й категорії тут лише для валідного XML.
  python tools/make_meloni.py "<шлях до xlsx>"   → meloni.json"""
import json, os, re, sys, time
import openpyxl, requests

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'

ws = openpyxl.load_workbook(sys.argv[1], read_only=True).active
rows = list(ws.iter_rows(values_only=True))
h = {k: i for i, k in enumerate(rows[0])}
items, cats = [], {}
for r in rows[1:]:
    key = (r[h['ID з прайсу продавця']] or '').strip()
    if not key.startswith('MLN'):
        continue
    url = r[h['Посилання на сайт']]
    page = requests.get(url.replace('rozetka.com.ua/', 'rozetka.com.ua/ua/'), headers={'User-Agent': UA}, timeout=60).text
    pic = re.search(r'https://content\d*\.rozetka\.com\.ua/goods/images/big/\d+\.(?:jpg|png|webp)', page)
    live = re.search(r'"price":(\d+)', page)
    cid = str(r[h['ID категорії у прайсі продавця']])
    cats[cid] = r[h['Категорія з прайсу продавця']]
    items.append({'id': key, 'rozetka_id': r[h['Rozetka ID']], 'name': r[h['Назва товару']], 'name_ua': r[h['Назва товару UA']],
                  'category': cid, 'price': r[h['Стара ціна']], 'rozetka_price_16_11': int(live.group(1)) if live else None,
                  'available': r[h['Наявність']] == 'В наявності', 'picture': pic.group(0) if pic else None, 'url': url})
    time.sleep(1)
json.dump({'_': __doc__.split('\n')[0], 'categories': cats, 'items': items}, open(os.path.join(ROOT, 'meloni.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print(len(items), 'товарів;', 'без фото:', [i['id'] for i in items if not i['picture']],
      '; ціна Розетки ≠ стара ціна файлу:', [(i['id'], i['price'], i['rozetka_price_16_11']) for i in items if i['price'] != i['rozetka_price_16_11']])
