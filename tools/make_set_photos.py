# -*- coding: utf-8 -*-
"""Білий фон для товарів без білих пакшотів (переважно набори): перше фото з сайту → KIE nano-banana-pro міняє фон
на білий, товари не чіпає (варіант «В», погоджено Olena 19.10) → фон доводимо до чистого білого → site/img/<арт>_1.jpg.
У фіді після нього йдуть решта фото сайту (URL). Результат: photos_sets.json (build_feed.py зливає його з photos.json).
  python tools/make_set_photos.py L056 L221 ...    (запускається локально; потрібні velsvisual і ключ KIE)"""
import os, sys, json, subprocess, shutil, glob, io, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'site', 'img'); WORK = os.path.join(ROOT, 'work_sets')
EXPORT = r'C:\Users\nomer\lunnitsa-site\work\feed\live_export_20261019_after.json'
VV = shutil.which('velsvisual') or 'velsvisual'
H = {'User-Agent': 'Mozilla/5.0 Chrome/141.0', 'Cookie': 'challenge_passed=4d5ade3eca539ceaa4b50b47ae801beb78b32e089ad09ae0b291a9469af5e8ff'}
PROMPT = ('Edit this product photo: replace the beige/pink background and the beige surface with a pure white seamless studio '
          'background (#FFFFFF) and a white surface, like a marketplace packshot. Keep the products EXACTLY as they are: same '
          'arrangement, positions, sizes, overlaps, caps, labels and all label text unchanged, do not redraw or retouch the '
          'packaging. Keep only a soft natural grey contact shadow under the products, remove the coloured light and coloured '
          'reflections. No added objects, text or watermarks.')


def whiten(im):
    """Світло-сірий фон KIE → білий м'якою кривою: тони до 200 не змінюються, від 200 до тону фону (медіана рамки)
    розтягуються до 255. Якщо фон уже білий (whiteness ≥ 0.97) — не чіпаємо. (19.10: жорсткий поріг стирав
    блідий рожевий кварц L203, заливка від краю давала плями, лінійне підняття випалювало білі флакони.)"""
    from make_photos import whiteness
    tmp = io.BytesIO(); im.save(tmp, 'PNG'); tmp.seek(0)
    if whiteness(tmp) >= 0.97:
        return im
    w, h = im.size; b = max(4, int(min(w, h) * 0.04)); px = []
    for box in ((0, 0, w, b), (0, 0, b, h), (w - b, 0, w, h)):
        px += [min(p) for p in im.crop(box).get_flattened_data()]
    px.sort(); bg = max(215, min(252, px[len(px) // 2]))
    lut = [v if v <= 200 else min(255, round(200 + (v - 200) * 55 / (bg - 200))) for v in range(256)] * 3
    return im.point(lut)


def similar(f1, f2):
    """Кореляція контурів 64×64: свій результат ≥ 0.9, чужий ≤ 0.8."""
    import math
    from PIL import ImageFilter
    vs = []
    for f in (f1, f2):
        v = list(ImageOps.exif_transpose(Image.open(f)).convert('L').resize((64, 64)).filter(ImageFilter.FIND_EDGES).get_flattened_data())
        m = sum(v) / len(v); v = [x - m for x in v]; n = math.sqrt(sum(x * x for x in v)) or 1; vs.append([x / n for x in v])
    return sum(x * y for x, y in zip(*vs))


def one(a, url):
    os.makedirs(os.path.join(WORK, a), exist_ok=True)
    # унікальна назва: KIE-завантажувач плутає однакові імена файлів при паралельних запусках (19.10: 17 з 28 переплутано)
    src = os.path.join(WORK, a, '%s_site_1.jpg' % a)
    Image.open(io.BytesIO(requests.get(url, headers=H, timeout=60).content)).convert('RGB').save(src, quality=95)
    out = os.path.join(WORK, a, 'kie')
    shutil.rmtree(out, ignore_errors=True)
    r = subprocess.run([VV, 'run', 'nano-banana-pro', '--prompt', PROMPT, '--set', 'image_input=["%s"]' % src.replace('\\', '/'),
                        '--set', 'aspect_ratio=1:1', '--set', 'resolution=2K', '--set', 'output_format=jpg',
                        '--wait', '--timeout', '600', '--download', out, '--json'], capture_output=True, text=True, encoding='utf-8')
    got = glob.glob(os.path.join(out, '*.jpg'))
    if not got:
        return a, 'помилка KIE: ' + (r.stdout + r.stderr)[-300:]
    if similar(got[0], src) < 0.85:
        return a, 'НЕ ЗБІГАЄТЬСЯ з фото сайту (%.2f), не ставлю' % similar(got[0], src)
    im = ImageOps.exif_transpose(Image.open(got[0])).convert('RGB'); im.thumbnail((1600, 1600)); im = whiten(im)
    im.save(os.path.join(IMG, '%s_1.jpg' % a), quality=86, optimize=True)
    shutil.copy(os.path.join(IMG, '%s_1.jpg' % a), os.path.join(WORK, a, 'white.jpg')); shutil.copy(src, os.path.join(WORK, a, 'site_1.jpg'))
    return a, 'ok'


def main(arts):
    L = {}
    for p in json.load(open(EXPORT, encoding='utf-8')):
        L.setdefault(p['article'].strip(), p)
    path = os.path.join(ROOT, 'photos_sets.json')
    sets = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
    jobs = {a: L[a]['images'] for a in arts if L.get(a) and L[a]['images']}
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda a: one(a, jobs[a][0]), jobs))
    for a, msg in res:
        print(a, msg)
        if msg == 'ok':
            sets[a] = ['%s_1.jpg' % a] + jobs[a][1:7]  # біле фото + решта фото сайту
    json.dump(sets, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1:])
