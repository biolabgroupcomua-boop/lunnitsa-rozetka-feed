# -*- coding: utf-8 -*-
"""Перевірка site/rozetka.xml за вимогами Розетки до XML (sellerhelp.rozetka.com.ua/p185-pricelist-requirements.html).
python tools/check_feed.py [файл]  → список порушень; код виходу 1, якщо є порушення."""
import re, sys, os, collections
import xml.etree.ElementTree as ET

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
for n, c in names.items():
    if c > 1:
        bad['однакові назви'].append('%s ×%d' % (n[:70], c))
if bad:
    for k, v in bad.items():
        print('✗ %s: %d  %s' % (k, len(v), '; '.join(v[:6])))
    sys.exit(1)
print('✓ порушень немає: %d товарів' % len(shop.find('offers')))
