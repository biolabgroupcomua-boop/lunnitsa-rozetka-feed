# -*- coding: utf-8 -*-
"""Перевірка site/rozetka.xml за вимогами Розетки (sellerhelp.rozetka.com.ua: p185 XML, p217 назва, p212 опис, p210 характеристики, p216 фото).
python tools/check_feed.py [файл]  → список порушень; код виходу 1, якщо є порушення."""
import re, sys, os, collections
import xml.etree.ElementTree as ET
try:
    from PIL import Image
except ImportError:
    Image = None
DESC_TAGS = {'strong', 'b', 'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'table', 'tbody', 'tr', 'td', 'th', 'div', 'span'}

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'site', 'rozetka.xml')
raw = open(path, encoding='utf-8').read()
bad = collections.defaultdict(list)
if not raw.startswith('<?xml version="1.0" encoding="UTF-8"?>'):
    bad['початок файлу'].append('немає <?xml version="1.0" encoding="UTF-8"?>')
if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', raw):
    bad['недруковані символи 0-31'].append(str(len(re.findall(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', raw))))
outside = re.sub(r'<!\[CDATA\[.*?\]\]>', '', raw, flags=re.S)
if "'" in re.sub(r'<[^>]+>', '', outside):
    bad["символ ' не замінено на &apos;"].append(str(re.sub(r'<[^>]+>', '', outside).count("'")))
root = ET.fromstring(raw.replace('<!DOCTYPE yml_catalog SYSTEM "shops.dtd">', '').encode('utf-8'))
shop = root.find('shop')
if not re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', root.get('date', '')):
    bad['yml_catalog date'].append(root.get('date', ''))
for tag in ('currencies', 'categories', 'offers'):
    if shop.find(tag) is None:
        bad['shop'].append('немає <%s>' % tag)
cats = {c.get('id') for c in shop.find('categories')}
names = collections.Counter()
for o in shop.find('offers'):
    i = o.get('id', '')
    if not re.fullmatch(r'[A-Za-z0-9]+', i):
        bad['id лише латиниця й цифри, без пробілів'].append(repr(i))
    if o.get('available') not in ('true', 'false'):
        bad['available'].append(i)
    for t in ('price', 'currencyId', 'categoryId', 'vendor', 'name', 'description'):
        if o.find(t) is None or not (o.find(t).text or '').strip():
            bad['немає <%s>' % t].append(i)
    if o.find('categoryId') is not None and o.find('categoryId').text not in cats:
        bad['categoryId не з переліку категорій'].append(i)
    if o.find('stock_quantity') is None:
        bad['немає <stock_quantity>'].append(i)
    po = o.find('price_old')
    if po is not None and float(po.text) <= float(o.find('price').text):
        bad['price_old не більша за price'].append(i)
    pics = [p.text or '' for p in o.findall('picture')]
    if not 1 <= len(pics) <= 15:
        bad['фото 1-15'].append('%s: %d' % (i, len(pics)))
    for u in pics:
        if not u.startswith('https://') or re.search(r'[А-Яа-яЁёІіЇїЄєҐґ\s]', u) or len(u) > 1999:
            bad['фото: https, без кирилиці й пробілів'].append('%s %s' % (i, u[:90]))
    for t in ('name', 'name_ua'):
        n = (o.findtext(t) or '')
        if len(n) > 255:
            bad['%s > 255' % t].append(i)
    names[o.findtext('name')] += 1
    for t in ('description', 'description_ua'):
        if len(o.findtext(t) or '') > 50000:
            bad['%s > 50000' % t].append(i)
    if o.find('url') is not None and len(o.findtext('url')) > 500:
        bad['url > 500'].append(i)
    for p in o.findall('param'):
        v = p.text or ''
        if not p.get('name') or not v.strip():
            bad['param без назви чи значення'].append(i)
        if len(v) > 500:
            bad['param > 500 знаків'].append('%s %s (%d)' % (i, p.get('name'), len(v)))
    # p217 назва: без розділових знаків і спецсимволів (артикул у дужках дозволено), бренд у назві = <vendor>
    vendor = o.findtext('vendor') or ''
    for t in ('name', 'name_ua'):
        n = o.findtext(t) or ''
        if re.search(r'[,.:;«»"№×%+!*™@^½λΩ]', re.sub(r'\s\([A-Za-z0-9]+\)$', '', n)):
            bad['%s: розділові знаки або спецсимволи' % t].append('%s %s' % (i, n[:60]))
        if vendor and vendor not in n:
            bad['%s: немає бренду з <vendor>' % t].append(i)
        if re.search(r'подарун|подарок|акці|знижк|новинк|розпродаж|хіт|оригінал', n, re.I):
            bad['%s: рекламні слова' % t].append(i)
    if not (o.findtext('article') or '').strip():
        bad['немає <article>'].append(i)
    # p212 опис: HTML у CDATA, лише дозволені теги, без посилань, emoji і подарунків/знижок
    for t in ('description', 'description_ua'):
        d = o.findtext(t) or ''
        if not d.lstrip().startswith('<'):
            bad['%s без HTML-розмітки' % t].append(i)
        other = set(x.lower() for x in re.findall(r'</?\s*([a-zA-Z0-9]+)', d)) - DESC_TAGS
        if other:
            bad['%s: теги поза переліком Розетки' % t].append('%s %s' % (i, ','.join(sorted(other))))
        if re.search(r'https?://|www\.|<a\b|lunnitsa\.com', d, re.I):
            bad['%s: посилання' % t].append(i)
        if re.search('[\U0001F300-\U0001FAFF☀-➿]', d):
            bad['%s: emoji' % t].append(i)
        if re.search(r'\bподарун(?:ок|ком|ка)\b|\bподар(?:ок|ком|ка)\b|знижк|скидк|доставк', d, re.I):
            bad['%s: подарунок, знижка чи доставка' % t].append(i)
    if len(o.findall('param')) < 3:
        bad['характеристик менше 3 (p210)'].append(i)
    # p216 фото: 400–4000 px, до 10 МБ (перевіряємо свої файли з site/img, якщо є Pillow)
    for u in pics:
        f = os.path.join(ROOT, 'site', 'img', u.rsplit('/', 1)[-1]) if '/lunnitsa-rozetka-feed/img/' in u else None
        if f and Image and os.path.exists(f):
            w, h = Image.open(f).size
            if min(w, h) < 400 or max(w, h) > 4000 or os.path.getsize(f) > 10 * 2 ** 20:
                bad['фото: розмір 400–4000 px, до 10 МБ'].append('%s %s %dx%d' % (i, u.rsplit('/', 1)[-1], w, h))
used = {o.findtext('categoryId') for o in shop.find('offers')}
warn = []
for c in shop.find('categories'):
    if len(c.text or '') > 255:
        bad['назва категорії > 255'].append(c.get('id'))
    if c.get('id') not in used:
        bad['категорія без товарів'].append('%s %s' % (c.get('id'), c.text))
    if not c.get('rz_id'):  # не блокує: новий товар без запису в categories.json лишається в категорії Horoshop
        warn.append('%s %s' % (c.get('id'), c.text))
if warn:
    print('! категорії без rz_id (дописати товар у categories.json): %s' % '; '.join(warn))
# p398: у товарі щонайменше 2 характеристики з назвами Розетки його категорії (інакше Pricecreator не пустить у XML)
import json
RZP = json.load(open(os.path.join(ROOT, 'rozetka_category_params.json'), encoding='utf-8'))
few = [o.get('id') for o in shop.find('offers')
       if len({p.get('name') for p in o.findall('param')} & set(RZP.get(o.findtext('categoryId'), {}))) < 2]
if few:
    print('! менше 2 характеристик Розетки: %s' % ', '.join(few))
names_ua = collections.Counter(o.findtext('name_ua') for o in shop.find('offers'))
for n, c in names_ua.items():
    if c > 1:
        bad['однакові назви name_ua'].append('%s ×%d' % ((n or '')[:70], c))
for n, c in names.items():
    if c > 1:
        bad['однакові назви'].append('%s ×%d' % (n[:70], c))
if bad:
    for k, v in bad.items():
        print('✗ %s: %d  %s' % (k, len(v), '; '.join(v[:6])))
    sys.exit(1)
print('✓ порушень немає: %d товарів' % len(shop.find('offers')))
