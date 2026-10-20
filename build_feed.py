# -*- coding: utf-8 -*-
"""Фід Розетки для Lunnitsa з білими фото. Запускає GitHub Actions щогодини (.github/workflows/feed.yml).
1. Бере фід Розетки, який Horoshop генерує щоночі: категорії, назви, описи.
2. З API Horoshop бере актуальні кількість, наявність, звичайну ціну, назви й описи UA/RU і характеристики (<param>). Знижок на Розетку не передаємо
   (Olena 19.10: «Розетка дає свої знижки»): price = ціна сайту без знижок, price_old прибираємо.
3. Ставить фото з site/img (photos.json; набори — photos_sets.json, білий фон зроблено в KIE з фото сайту): перше на білому.
   Товари без білих фото лишаються з фото сайту.
4. Пише site/rozetka.xml і site/status.json. Якщо щось не вдалося — падає, і на Pages лишається попередній фід.
Змінні середовища: HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD, BASE_URL (адреса Pages, зі слешем у кінці)."""
import os, re, sys, json, time, datetime, requests
import rozetka_rules as R

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


def get_products():
    s = requests.Session(); s.headers['User-Agent'] = UA
    tok = s.post(D + '/api/auth', json={'login': os.environ['HOROSHOP_LOGIN'], 'password': os.environ['HOROSHOP_PASSWORD']}, timeout=60).json()['response']['token']
    out, off = {}, 0
    while True:
        r = s.post(D + '/api/catalog/export/', json={'token': tok, 'offset': off, 'limit': 500}, timeout=180).json()['response']['products']
        for p in r:
            out[p['article']] = p
        if len(r) < 500:
            return out
        off += 500


def esc(t):
    return (t or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')


def cval(v, lang='ru'):
    """Значення характеристики Horoshop: {'value': {'ru':…}} / {'ru':…} / список."""
    if isinstance(v, dict) and 'value' in v:
        v = v['value']
    if isinstance(v, dict):
        return (v.get(lang) or v.get('ru') or v.get('ua') or '').strip()
    if isinstance(v, list):
        return '; '.join(filter(None, (cval(x, lang) for x in v)))
    return str(v or '').strip()


HAIR = ('волос', 'шампун', 'кондиционер')
# тип волосся: на сайті такої характеристики немає, беремо з hair_types.json (визначено з назв і описів)
HAIR_TYPES = {k: v for k, v in json.load(open(os.path.join(ROOT, 'hair_types.json'), encoding='utf-8')).items() if not k.startswith('_')}


def params(p):
    """Характеристики для Розетки (назви полів як у фідах інших брендів на Розетці, напр. Melony): країна, склад,
    об'єм/вага, тип шкіри чи волосся, дія, призначення, EAN."""
    ch = p.get('characteristics') or {}
    out = []
    def add(n, v, multi=False):
        """Вимоги Розетки: значення ≤ 500 знаків; кілька значень — через <br> у CDATA."""
        v = (v or '').strip()
        if not v:
            return
        if multi and re.search(r'[,;]', v):
            vals = [x.strip() for x in re.split(r'[,;]', v) if x.strip()]
            out.append('<param name="%s"><![CDATA[%s]]></param>' % (n, '<br>'.join(vals)[:500]))
            return
        if len(v) > 500:  # склад: обрізаємо по останній комі, повний склад є в описі
            v = v[:497].rsplit(',', 1)[0] + '…'
        out.append('<param name="%s">%s</param>' % (n, esc(v)))
    add('Страна-производитель товара', cval(ch.get('country')))
    add('Состав', cval(ch.get('processor')))
    vol = cval(ch.get('ves')) or cval(ch.get('vid')).split(',')[-1].strip()
    if re.search(r'\d\s*(мл|л)', vol):
        add('Объем', re.search(r'[\d.,]+\s*(мл|л)', vol).group(0))
    elif re.search(r'\d\s*(г|кг|гр)', vol):
        add('Вес', re.search(r'[\d.,]+\s*(г|кг|гр)', vol).group(0))
    hair = HAIR_TYPES.get((p.get('article') or '').strip())
    if hair:
        add('Тип волос', hair, True)
    else:
        kind = (cval(ch.get('produkty')) + ' ' + cval(ch.get('kategorija')) + ' ' + cval(ch.get('primenenie'))).lower()
        add('Тип волос' if any(h in kind for h in HAIR) else 'Тип кожи', cval(ch.get('tipKozhi')), True)
    add('Действие', cval(ch.get('deystvie')), True)
    add('Назначение', cval(ch.get('primenenie')), True)
    add('EAN', (p.get('gtin') or '').strip())
    return out


def categories(xml, st):
    """Категорії Розетки замість категорій Horoshop (categories.json): id = rz_id = ID кінцевої категорії на rozetka.com.ua.
    Товар без запису в categories.json лишається в категорії Horoshop (status.json → no_category)."""
    cats = json.load(open(os.path.join(ROOT, 'categories.json'), encoding='utf-8'))['categories']
    where = {art: c['id'] for c in cats for art in c['items']}
    st['no_category'] = []
    used = set()

    def offer(m):
        o = m.group(0)
        art = re.search(r'<offer id="([^"]+)"', o).group(1)
        if art in where:
            o = re.sub(r'<categoryId>[^<]*</categoryId>', '<categoryId>%s</categoryId>' % where[art], o, count=1)
        else:
            st['no_category'].append(art)
        used.add(re.search(r'<categoryId>([^<]+)</categoryId>', o).group(1).strip())
        return o

    xml = re.sub(r'<offer\b.*?</offer>', offer, xml, flags=re.S)
    m = re.search(r'([ \t]*)<categories>(.*?)</categories>', xml, re.S)
    ind = m.group(1) + '\t'
    # категорії Horoshop лишаються лише для товарів без запису в categories.json
    old = [c for c in re.findall(r'<category\b[^>]*>[^<]*</category>', m.group(2)) if re.search(r'id="([^"]+)"', c).group(1) in used]
    # rz_id: автоматична прив'язка до категорії Розетки (p185)
    ours = ['<category id="%s" rz_id="%s">%s</category>' % (c['id'], c['id'], esc(c['name'])) for c in cats if c['id'] in used]
    block = '%s<categories>\n%s\n%s</categories>' % (m.group(1), '\n'.join(ind + c for c in ours + old), m.group(1))
    return xml[:m.start()] + block + xml[m.end():]


def main():
    xml = get_feed()
    stock = get_products()
    photos = json.load(open(os.path.join(ROOT, 'photos.json'), encoding='utf-8'))
    sets_path = os.path.join(ROOT, 'photos_sets.json')  # набори: біле фото з KIE + решта фото сайту (URL)
    if os.path.exists(sets_path):
        photos.update(json.load(open(sets_path, encoding='utf-8')))
    st = {'white_photos': 0, 'site_photos': [], 'stock_updated': 0, 'not_in_api': []}

    def offer(m):
        o = m.group(0)
        art = re.search(r'<offer id="([^"]+)"', o).group(1)
        key = art.strip()
        if art in stock:
            p = stock[art]
            q, pres, price = int(float(p.get('quantity') or 0)), (p.get('presence') or {}).get('id'), float(p.get('price') or 0)
            avail = 'true' if pres == 1 and q > 0 else 'false'
            o = re.sub(r'available="\w+"', 'available="%s"' % avail, o, count=1)
            o = re.sub(r'<stock_quantity>[^<]*</stock_quantity>', '<stock_quantity>%d</stock_quantity>' % max(0, min(q, MAX_QTY)), o, count=1)
            if price > 0:
                o = re.sub(r'<price>[^<]*</price>', '<price>%s</price>' % ('%g' % price), o, count=1)
            o = re.sub(r'\s*<price_old>[^<]*</price_old>', '', o)
            # назва й опис: name/description російською, name_ua/description_ua українською (вимога YML Розетки)
            rt, md = p.get('rozetka_title') or {}, p.get('marketplace_description') or {}
            # назва за формулою Розетки (p217), опис з HTML-розміткою (p212): rozetka_rules.py
            names = {L: R.name((rt.get(L) or (p.get('title') or {}).get(L) or '').strip(), key) for L in ('ru', 'ua')}
            descs = {L: R.html((md.get(L) or '').replace(']]>', ']] >').strip()) for L in ('ru', 'ua')}
            ean_horoshop = (re.search(r'<param name="EAN">([^<]+)</param>', o) or [None, ''])[1].strip()  # штрихкод із картки, якого немає в API
            if ean_horoshop and not (p.get('gtin') or '').strip():
                p = dict(p, gtin=ean_horoshop)
            o = re.sub(r'\s*<(name|name_ua|description|description_ua|param)\b[^>]*>.*?</\1>', '', o, flags=re.S)
            block = ['<name>%s</name>' % esc(names['ru'] or names['ua']), '<name_ua>%s</name_ua>' % esc(names['ua'] or names['ru']),
                     '<description><![CDATA[%s]]></description>' % (descs['ru'] or descs['ua']),
                     '<description_ua><![CDATA[%s]]></description_ua>' % (descs['ua'] or descs['ru'])] + params(p)
            o = re.sub(r'\s*</offer>$', '', o) + '\n' + ''.join('\t\t\t\t%s\n' % x for x in block) + '\t\t\t</offer>'
            o = re.sub(r'<offer id="([^"]+)"', lambda m: '<offer id="%s"' % re.sub(r'[^A-Za-z0-9]', '', m.group(1)), o, count=1)
            # бренд у <vendor> = бренд у назві (p217); у Horoshop у двох товарів LELYA стоїть «promo»
            o = re.sub(r'\s*<vendor>[^<]*</vendor>', '', o)
            o = o.replace('<stock_quantity>', '<vendor>Lunnitsa</vendor>\n\t\t\t\t<article>%s</article>\n\t\t\t\t<stock_quantity>' % esc(key), 1)
            st['stock_updated'] += 1
            st['params'] = st.get('params', 0) + len(block) - 4
        else:
            st['not_in_api'].append(key)
        if key in photos:
            pics = ''.join('<picture>%s</picture>' % (f if f.startswith('http') else BASE + 'img/' + f) for f in photos[key])
            o = re.sub(r'(\s*<picture>[^<]*</picture>)+', '\n\t\t\t\t' + pics.replace('</picture><picture>', '</picture>\n\t\t\t\t<picture>'), o, count=1)
            st['white_photos'] += 1
        else:
            st['site_photos'].append(key)
        return o

    xml, n = re.subn(r'<offer\b.*?</offer>', offer, xml, flags=re.S)
    if n == 0:
        raise SystemExit('у фіді Horoshop немає товарів')
    xml = categories(xml, st)
    # p185: date = час генерації або зміни файлу; Horoshop ставить час нічного фіду, а ми оновлюємо щогодини
    st['horoshop_feed_date'] = (re.search(r'yml_catalog date="([^"]+)"', xml) or [None, ''])[1]
    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo('Europe/Kyiv'))
    except Exception:
        now = datetime.datetime.now(datetime.timezone.utc)
    xml = re.sub(r'yml_catalog date="[^"]*"', 'yml_catalog date="%s"' % now.strftime('%Y-%m-%d %H:%M'), xml, count=1)
    os.makedirs(os.path.join(ROOT, 'site'), exist_ok=True)
    open(os.path.join(ROOT, 'site', 'rozetka.xml'), 'w', encoding='utf-8').write(xml)
    st.update({'offers': n, 'built_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')})
    json.dump(st, open(os.path.join(ROOT, 'site', 'status.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    import subprocess
    chk = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'check_feed.py')], capture_output=True, text=True, encoding='utf-8')
    print(chk.stdout.strip())
    if chk.returncode:
        raise SystemExit('фід не пройшов перевірку правил Розетки')
    print('товарів %d | білі фото %d | фото сайту %d | кількість з API %d | немає в API %d' % (
        n, st['white_photos'], len(st['site_photos']), st['stock_updated'], len(st['not_in_api'])))


if __name__ == '__main__':
    main()
