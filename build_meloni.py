# -*- coding: utf-8 -*-
"""Фід Meloni для Pricecreator (16.11.2026): site/meloni.xml = фід сайту Meloni (Horoshop, джерело Pricecreator 31549) + знижка з discounts.json.
Навіщо: знижку на Розетці ставить лише стара ціна з XML (p328, p390), а фід Horoshop Meloni її не дає; ручний режим прайс-листа зупинив би
оновлення з XML і для Лунниці (прайс-лист спільний). Тому товари Meloni в Pricecreator стоять на джерелі 34332 (цей файл), а все інше —
назви, категорії, наявність — береться з фіду сайту без змін. Поза періодом знижки файл = фід сайту без price_old.
Адреса фіду сайту з ключем — у змінній MELONI_FEED (репо публічне). OUT_DIR — як у build_feed.py."""
import os, re, sys
from xml.dom import minidom
import requests
from build_feed import UA, discount, kyiv_now

sys.stdout.reconfigure(encoding='utf-8')
OUT = os.environ.get('OUT_DIR') or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'site')


def main():
    r = requests.get(os.environ['MELONI_FEED'], headers={'User-Agent': UA}, timeout=120)
    r.encoding = 'utf-8'
    if r.status_code != 200 or '<yml_catalog' not in r.text:
        raise SystemExit('фід Meloni: %s, не XML' % r.status_code)
    now = kyiv_now().strftime('%Y-%m-%d %H:%M')
    st = {'offers': 0, 'discounts': 0, 'skipped': []}

    def fix(m):
        o = m.group(0)
        key = re.search(r'<offer id="([^"]+)"', o).group(1).strip()
        price = float(re.search(r'<price>([^<]*)</price>', o).group(1))
        o = re.sub(r'\s*<price_old>[^<]*</price_old>', '', o)
        dc = discount(key, price, now)
        if dc == 'skip':
            st['skipped'].append(key)
        elif dc:
            o = re.sub(r'<price>[^<]*</price>', '<price>%g</price>\n\t\t\t\t<price_old>%g</price_old>' % (dc[1], dc[0]), o, count=1)
            st['discounts'] += 1
        st['offers'] += 1
        return o

    xml = re.sub(r'<offer .*?</offer>', fix, r.text, flags=re.S)
    if not st['offers']:
        raise SystemExit('у фіді Meloni немає товарів')
    minidom.parseString(xml.encode('utf-8'))   # невалідний XML не публікуємо
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, 'meloni.xml'), 'w', encoding='utf-8').write(xml)
    print('meloni.xml: %(offers)d товарів, зі знижкою %(discounts)d, ціна сайту ≠ затвердженій: %(skipped)s' % st)


if __name__ == '__main__':
    main()
