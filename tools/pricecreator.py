# -*- coding: utf-8 -*-
"""Кабінет Pricecreator Розетки (pricecreator.rozetka.com.ua) для Лунниці: перевірка й налаштування через браузер
без вікна (Playwright). Кабінет СПІЛЬНИЙ з Melony: скрипт працює лише з категоріями з categories.json і джерелом
нашого фіду; категорії Melony (2120, 2129, 3659, 3764, 4626) і її автооновлення не чіпає.
Доступ: змінні середовища PC_LOGIN, PC_PASSWORD (пароль у файли не записувати).

  python tools/pricecreator.py check               # лише читає: помилки, у XML, автооновлення, останнє звернення Розетки
  python tools/pricecreator.py import              # імпорт нашого фіду (без «вимкнути відсутні» й інших галочок)
  python tools/pricecreator.py setup [id ...]      # у категоріях Лунниці: увімкнути поля Розетки з фіду, «Оновити зв'язки»
  python tools/pricecreator.py compare [id ...]    # «Порівняння» параметрів у категоріях Лунниці
  python tools/pricecreator.py xml [--go]          # перенести товари Лунниці в XML (без --go лише показує, що перенесе)
Порядок після змін у фіді: import → setup → compare → xml --go → check. Назву, опис і категорію Pricecreator бере
лише з ПЕРШОГО імпорту; щоб їх змінити, товари видаляють і очищають кошик (див. ROZETKA_PRICECREATOR.md)."""
import os, re, sys, json, collections
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = 'https://pricecreator.rozetka.com.ua/'
FEED_LINK = 'lunnitsa-rozetka-feed'
MELONY = {'2120', '2129', '3659', '3764', '4626'}
# парфуми: Розетка вимагає документи (sellerhelp p797); у XML лише після їх подання
HOLD = {'L243', 'L245', 'L327', 'L328'}
CATS = json.load(open(os.path.join(ROOT, 'categories.json'), encoding='utf-8'))['categories']
LUN_CATS = [c['id'] for c in CATS]
LUN_ITEMS = {a for c in CATS for a in c['items']}
PCP = {k: {p['name']: p['id'] for p in v['params']}
       for k, v in json.load(open(os.path.join(ROOT, 'pricecreator_params.json'), encoding='utf-8')).items() if not k.startswith('_')}


def session(p):
    b = p.chromium.launch(headless=True)
    ctx = b.new_context(viewport={'width': 1600, 'height': 1000}, locale='uk-UA')
    pg = ctx.new_page()
    pg.on('dialog', lambda d: d.accept())
    pg.goto(BASE, wait_until='networkidle', timeout=90000)
    pg.get_by_text('Особистий кабінет').first.click()
    pg.wait_for_timeout(2500)
    pg.fill('input[name=email]:visible', os.environ['PC_LOGIN'])
    pg.fill('input[name=pwd]', os.environ['PC_PASSWORD'])
    pg.press('input[name=pwd]', 'Enter')
    pg.wait_for_url('**/seller/**', timeout=60000)
    return b, pg


def go(pg, path):
    pg.goto(BASE + path, wait_until='networkidle', timeout=90000)


def source_id(pg):
    """id джерела нашого фіду на сторінці імпорту (у Melony своє)."""
    go(pg, 'seller/import/xml/')
    for el in pg.query_selector_all('span.prepareImportSource2'):
        if FEED_LINK in (el.get_attribute('data-link') or ''):
            return el.get_attribute('data-source')
    raise SystemExit('джерело нашого фіду не знайдено на сторінці імпорту')


def edit_links(pg):
    """id категорії Розетки → сторінка налаштування категорії в кабінеті."""
    go(pg, 'seller/categories')
    out = {}
    for tr in pg.query_selector_all('tr[data-cid]'):
        btn = tr.query_selector('span.checkAllParamsInCat')
        if btn:
            out[btn.get_attribute('data-categoryid')] = BASE + 'seller/categories/edit/%s/0' % tr.get_attribute('data-cid')
    return out


def feed_params():
    """Які характеристики наш фід передає в кожній категорії (з живого фіду)."""
    import urllib.request
    x = urllib.request.urlopen('https://biolabgroupcomua-boop.github.io/lunnitsa-rozetka-feed/rozetka.xml').read().decode('utf-8')
    used = collections.defaultdict(set)
    for o in re.findall(r'<offer .*?</offer>', x, re.S):
        c = re.search(r'<categoryId>([^<]+)', o).group(1)
        used[c] |= {n.replace('&apos;', "'") for n in re.findall(r'<param name="([^"]+)"', o)}
    return used


def check(pg):
    go(pg, 'seller/dashboard/')
    t = pg.inner_text('body')
    for k in ('В XML:', 'Нових:', 'Помилки:', "Товар не прив'язаний до категорії ROZETKA", 'Товару немає в наявності'):
        m = re.search(re.escape(k) + r'[^\n]*', t)
        print(m.group(0).strip() if m else k + ' ?')
    sid = source_id(pg)
    go(pg, 'seller/cron')
    print('автооновлення нашого фіду:', 'ввімкнене' if pg.is_checked('#use_for_cron_%s' % sid) else 'ВИМКНЕНЕ',
          '| годин:', pg.eval_on_selector_all('#form_%s input[name="hours[]"]:checked' % sid, 'e => e.length'))
    go(pg, 'seller/xmlfiles/')
    rows = [l for l in pg.inner_text('body').split('\n') if re.match(r'\d{4}-\d\d-\d\d \d\d:\d\d', l)]
    print('останнє звернення Розетки до XML:', rows[0] if rows else '?')


def do_import(pg):
    sid = source_id(pg)
    for cb in ('dectivateold', 'clearparent', 'clearimages'):
        assert not pg.is_checked('#%s%s' % (cb, sid))
    pg.click('#startImport%s' % sid)
    for _ in range(60):
        pg.wait_for_timeout(3000)
        r = pg.inner_text('#result%s' % sid)
        if 'Завершено' in r or 'омилк' in r:
            break
    print(' '.join(pg.inner_text('#result%s' % sid).split()))


def setup(pg, cats):
    links, used = edit_links(pg), feed_params()
    for c in cats:
        assert c not in MELONY and c in LUN_CATS
        go(pg, links[c][len(BASE):])
        assert ('Оригінальний ID: %s' % c) in pg.inner_text('body')
        on = []
        for name in sorted(used.get(c, ())):
            pid = PCP.get(c, {}).get(name)
            inp = pid and pg.query_selector('input.input_to_fill[data-rozparam="%s"]' % pid)
            if inp and not inp.is_checked():
                pg.eval_on_selector('#addparam_%s ins.iCheck-helper' % pid, 'e => e.click()')  # зберігається одразу
                pg.wait_for_timeout(300)
                on.append(name)
        pg.eval_on_selector('button.saveCategoryData', 'e => e.click()')  # шапка перекриває кнопку: клік через елемент
        pg.wait_for_timeout(1500)
        go(pg, links[c][len(BASE):])
        pg.eval_on_selector('button.updateShopRelation', 'e => e.click()')
        pg.wait_for_timeout(4000)
        print(c, 'увімкнено:', on or '—')


def compare(pg, cats):
    for c in cats:
        assert c not in MELONY and c in LUN_CATS
        go(pg, 'seller/categories')
        # поруч у рядку є «Видалити категорію» — клікаємо лише шестірню порівняння
        pg.eval_on_selector('span.checkAllParamsInCat[data-categoryid="%s"]' % c, 'e => e.click()')
        pg.wait_for_timeout(1500)
        btn = pg.query_selector('#checkAllParamsModal button.startCheck')
        assert btn.get_attribute('data-categoryid') == c and pg.is_checked('#radio_all')
        btn.evaluate('e => e.click()')
        for _ in range(30):
            pg.wait_for_timeout(2000)
            if pg.eval_on_selector('#mainProgress', 'e => e.style.width') == '100%':
                break
        print(c, 'порівняно')


def to_xml(pg, really):
    go(pg, 'seller/itemList')
    pg.query_selector('select:has(option:text-is("500"))').select_option('500')
    pg.wait_for_load_state('networkidle'); pg.wait_for_timeout(4000)
    moved, held, low, already = [], [], [], 0
    for r in pg.query_selector_all('tr.startRow'):
        idel, cb = r.query_selector('small[title=ORIGINAL_ID]'), r.query_selector('input.xmlRozetkaToggle')
        art = idel.inner_text().strip() if idel else ''
        if not cb or art not in LUN_ITEMS:
            continue
        if art in HOLD:
            held.append(art); continue
        if cb.is_checked():
            already += 1; continue
        if int(cb.get_attribute('data-params') or 0) < 2:
            low.append(art); continue
        if really:
            cb.evaluate('e => e.parentElement.querySelector("ins.iCheck-helper").click()')
            pg.wait_for_timeout(700)
        moved.append(art)
    print('%s: %d | вже в XML: %d | притримано (парфуми): %s | мало характеристик: %s'
          % ('перенесено' if really else 'буде перенесено', len(moved), already, held, low))


if __name__ == '__main__':
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else 'check'), [a for a in sys.argv[2:] if not a.startswith('--')]
    with sync_playwright() as p:
        b, pg = session(p)
        try:
            if cmd == 'check':
                check(pg)
            elif cmd == 'import':
                do_import(pg)
            elif cmd == 'setup':
                setup(pg, args or LUN_CATS)
            elif cmd == 'compare':
                compare(pg, args or LUN_CATS)
            elif cmd == 'xml':
                to_xml(pg, '--go' in sys.argv)
            else:
                raise SystemExit(__doc__)
        finally:
            b.close()
