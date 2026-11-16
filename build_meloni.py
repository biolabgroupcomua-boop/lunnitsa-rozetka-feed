# -*- coding: utf-8 -*-
"""Фід Meloni для Pricecreator (16.11.2026): site/meloni.xml з meloni.json.
Навіщо: знижку на Розетці ставить лише стара ціна з XML (p328, p390), а джерело Meloni в Pricecreator (31549) її не дає, ручний режим
прайс-листа зупинив би оновлення з XML і для Лунниці (прайс-лист у них спільний). Тому 25 товарів Meloni переносяться в Pricecreator
на це джерело, а знижку бере discounts.json, як у Лунниці. Поза періодом знижки — звичайна ціна без price_old.
Ключ товару = «ID з прайсу продавця» (MLN…): за ним Pricecreator впізнає товар. OUT_DIR — як у build_feed.py."""
import datetime, json, os, sys
from xml.dom import minidom
from xml.sax.saxutils import escape
from build_feed import discount, kyiv_now

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('OUT_DIR') or os.path.join(ROOT, 'site')


def main():
    m = json.load(open(os.path.join(ROOT, 'meloni.json'), encoding='utf-8'))
    now = kyiv_now().strftime('%Y-%m-%d %H:%M')
    cats = '\n'.join('\t\t\t<category id="%s" rz_id="%s">%s</category>' % (c, c, escape(n)) for c, n in m['categories'].items())
    offers, disc = [], 0
    for i in m['items']:
        dc = discount(i['id'], i['price'], now)
        dc = dc if isinstance(dc, tuple) else None
        disc += bool(dc)
        offers.append('\n'.join([
            '\t\t\t<offer id="%s" available="%s">' % (i['id'], 'true' if i['available'] else 'false'),
            '\t\t\t\t<url>%s</url>' % escape(i['url']),
            '\t\t\t\t<price>%g</price>' % (dc[1] if dc else i['price'])] +
            (['\t\t\t\t<price_old>%g</price_old>' % dc[0]] if dc else []) + [
            '\t\t\t\t<currencyId>UAH</currencyId>',
            '\t\t\t\t<categoryId>%s</categoryId>' % i['category'],
            '\t\t\t\t<picture>%s</picture>' % escape(i['picture']),
            '\t\t\t\t<vendor>Meloni</vendor>',
            '\t\t\t\t<article>%s</article>' % i['id'],
            '\t\t\t\t<stock_quantity>%d</stock_quantity>' % (999 if i['available'] else 0),
            '\t\t\t\t<name>%s</name>' % escape(i['name']),
            '\t\t\t\t<name_ua>%s</name_ua>' % escape(i['name_ua']),
            '\t\t\t</offer>']))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE yml_catalog SYSTEM "shops.dtd">\n<yml_catalog date="%s">\n\t<shop>\n'
           '\t\t<name>SOULSKIN</name>\n\t\t<company>Meloni</company>\n\t\t<url>https://meloni.com.ua</url>\n'
           '\t\t<currencies>\n\t\t\t<currency id="UAH" rate="1"/>\n\t\t</currencies>\n\t\t<categories>\n%s\n\t\t</categories>\n'
           '\t\t<offers>\n%s\n\t\t</offers>\n\t</shop>\n</yml_catalog>\n') % (now, cats, '\n'.join(offers))
    minidom.parseString(xml.encode('utf-8'))   # невалідний XML не публікуємо
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, 'meloni.xml'), 'w', encoding='utf-8').write(xml)
    print('meloni.xml: %d товарів, зі знижкою %d' % (len(offers), disc))


if __name__ == '__main__':
    main()
