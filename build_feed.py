# -*- coding: utf-8 -*-
"""Фід Розетки для Lunnitsa з білими фото. Запускає GitHub Actions щогодини (.github/workflows/feed.yml).
1. Бере фід Розетки, який Horoshop генерує щоночі: категорії, назви, описи.
2. З API Horoshop бере актуальні кількість, наявність і звичайну ціну. Знижок на Розетку не передаємо
   (Olena 19.10: «Розетка дає свої знижки»): price = ціна сайту без знижок, price_old прибираємо.
3. Ставить фото з site/img (photos.json): перше на білому. Товари без білих фото лишаються з фото сайту.
4. Пише site/rozetka.xml і site/status.json. Якщо щось не вдалося — падає, і на Pages лишається попередній фід.
Змінні середовища: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD, BASE_URL (адреса Pages, зі слешем у кінці)."""
import os, re, sys, json, time, datetime, requests

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.abspath(__file__))
D = os.environ.get('HOROSHOP_DOMAIN', 'https://lunnitsa.com').rstrip('/')
BASE = os.environ.get('BASE_URL', 'https://biolabgroupcomua-boop.github.io/lunnitsa-rozetka-feed/')
FEED = D + '/marketplace-integration/rozetka-feed/'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
MAX_QTY = 999  # як у фіді Horoshop


def get_feed():
    """Сайт спершу віддає скрипт захисту від ботів, який ставить куку challenge_passed: беремо її з відповіді."""
    s = requests.Session(); s.headers['User-Agent'] = UA
    for _ in range(3):
        r = s.get(FEED, timeout=120)
        r.encoding = 'utf-8'
        if r.status_code == 200 and '<yml_catalog' in r.text:
            return r.text
        m = re.search(r'defaultHash\s*=\s*"([0-9a-f]+)"', r.text)
        if not m:
            raise SystemExit('фід Horoshop: %s, не XML і не перевірка ботів' % r.status_code)
        s.cookies.set('challenge_passed', m.group(1), domain=D.split('//')[1], path='/')
        time.sleep(2)
    raise SystemExit('фід Horoshop: не пройшли перевірку ботів')


def get_stock():
    s = requests.Session(); s.headers['User-Agent'] = UA
    tok = s.post(D + '/api/auth', json={'login': os.environ['HOROSHOP_LOGIN'], 'password': os.environ['HOROSHOP_PASSWORD']}, timeout=60).json()['response']['token']
    out, off = {}, 0
    while True:
        r = s.post(D + '/api/catalog/export/', json={'token': tok, 'offset': off, 'limit': 500}, timeout=180).json()['response']['products']
        for p in r:
            out[p['article']] = (int(float(p.get('quantity') or 0)), (p.get('presence') or {}).get('id'), float(p.get('price') or 0))
        if len(r) < 500:
            return out
        off += 500


def main():
    xml = get_feed()
    stock = get_stock()
    photos = json.load(open(os.path.join(ROOT, 'photos.json'), encoding='utf-8'))
    st = {'white_photos': 0, 'site_photos': [], 'stock_updated': 0, 'not_in_api': []}

    def offer(m):
        o = m.group(0)
        art = re.search(r'<offer id="([^"]+)"', o).group(1)
        key = art.strip()
        if art in stock:
            q, pres, price = stock[art]
            avail = 'true' if pres == 1 and q > 0 else 'false'
            o = re.sub(r'available="\w+"', 'available="%s"' % avail, o, count=1)
            o = re.sub(r'<stock_quantity>[^<]*</stock_quantity>', '<stock_quantity>%d</stock_quantity>' % max(0, min(q, MAX_QTY)), o, count=1)
            if price > 0:
                o = re.sub(r'<price>[^<]*</price>', '<price>%s</price>' % ('%g' % price), o, count=1)
            o = re.sub(r'\s*<price_old>[^<]*</price_old>', '', o)
            st['stock_updated'] += 1
        else:
            st['not_in_api'].append(key)
        if key in photos:
            pics = ''.join('<picture>%simg/%s</picture>' % (BASE, f) for f in photos[key])
            o = re.sub(r'(\s*<picture>[^<]*</picture>)+', '\n\t\t\t\t' + pics.replace('</picture><picture>', '</picture>\n\t\t\t\t<picture>'), o, count=1)
            st['white_photos'] += 1
        else:
            st['site_photos'].append(key)
        return o

    xml, n = re.subn(r'<offer\b.*?</offer>', offer, xml, flags=re.S)
    if n == 0:
        raise SystemExit('у фіді Horoshop немає товарів')
    os.makedirs(os.path.join(ROOT, 'site'), exist_ok=True)
    open(os.path.join(ROOT, 'site', 'rozetka.xml'), 'w', encoding='utf-8').write(xml)
    st.update({'offers': n, 'horoshop_feed_date': (re.search(r'yml_catalog date="([^"]+)"', xml) or [None, ''])[1],
               'built_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')})
    json.dump(st, open(os.path.join(ROOT, 'site', 'status.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('товарів %d | білі фото %d | фото сайту %d | кількість з API %d | немає в API %d' % (
        n, st['white_photos'], len(st['site_photos']), st['stock_updated'], len(st['not_in_api'])))


if __name__ == '__main__':
    main()
