# -*- coding: utf-8 -*-
"""Білі фото для фіду Розетки з теки дизайнера (запускається локально, коли змінились фото).
Тека: OneDrive/DESIGNER/LUNNITSA/Сеты/MakeUp_Lunnitsa. Папку товару знаходимо за артикулом у назві папки або файлу,
решту — за таблицею FOLDERS. Перше фото мусить бути на білому (перевірка рамки кадру), далі ракурси, склад останнім.
  python tools/make_photos.py            → site/img/<артикул>_<n>.jpg + photos.json + photos_report.md"""
import os, re, json, sys
from PIL import Image, ImageOps, ImageStat

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = r'C:\Users\nomer\OneDrive\DESIGNER\LUNNITSA\Сеты\MakeUp_Lunnitsa'
IMG = os.path.join(ROOT, 'site', 'img')
MAX_SIDE, MAX_PICS = 1600, 8
MIN_SIDE = 400  # Розетка (p216): фото від 400×400 px; смужки складу з етикетки менші, їх не беремо
SKIP_DIRS = re.compile(r'старий|стари|cтарі|PSD', re.I)

# товари без артикула в назві папки чи файлу: артикул → папка (відносно SRC)
FOLDERS = {
    'L001': 'Минеральная ванна Detox с солью Эпсома и авокадо',
    'L006': 'Сіль для ванни SPA Троянда',
    'L007': 'Сіль для ванни SPA Лаванда',
    'L287': 'скраб клубника',
    'L327': ('10 ml_Parfume', 'Lunnitsa 10 ml'),
    'L328': ('10 ml_Parfume', 'Dana 10 ml'),
    'L248': 'сыворотка Calm',
    'L251': 'Пенка для умывания Lunnitsa деликатная',
    'L247': 'Day Eye cream',
    'L246': 'Night Eye cream',
    'L280': 'Face protector makeup',
    'L281': 'Body protector makeup',
    'L297': 'Гель/Shower Gel_Strawberry',
    'L334': 'пілінг-диски Lelya',
    'L333': 'Acne Stop_Lelya',
    'L347': 'Гель/Shower Gel_Eucalyptus Mint',
    'L348': "Лосьйон для тіла Евкаліпт М'ята",
    'L350': 'Hand Cream_Eucalyptus Mint',
    'L349': "Скраб Евкаліпт М'ята",
    'L332': ('епсом соль', 'Salt_Makeup_Epsom-1000'),
    'L361': 'Hand Cream_Strawberry',
    'L357': 'Лосьйон для тіла Полуниця',
}


def is_img(f):
    return f.lower().endswith(('.jpg', '.jpeg', '.png'))


def whiteness(path):
    """Частка світлих пікселів на рамці кадру (5% з кожного боку): 1.0 = чисто білий фон."""
    im = ImageOps.exif_transpose(Image.open(path)).convert('L'); im.thumbnail((400, 400))
    w, h = im.size; b = max(2, int(min(w, h) * 0.05))
    px = []
    for box in ((0, 0, w, b), (0, h - b, w, h), (0, 0, b, h), (w - b, 0, w, h)):
        px += list(im.crop(box).get_flattened_data())
    return sum(1 for v in px if v >= 235) / len(px)


def rank(f, art):
    n = f.lower()
    if re.search(r'inci|состав|сосав|состаав', n):
        return 9  # склад останнім
    if (art and art.lower() in n) or re.search(r'make ?up|мейк|_1\b|top', n):
        return 0
    if re.match(r'^\d', n):
        return 5
    return 3


def by_article():
    found = {}
    for dp, dn, fn in os.walk(SRC):
        rel = os.path.relpath(dp, SRC)
        if SKIP_DIRS.search(rel):
            continue
        for f in fn:
            if not is_img(f):
                continue
            for a in set(re.findall(r'(L\d{3})(?!\d)', os.path.join(rel, f))):
                found.setdefault(a, set()).add(rel)
    out = {}
    for a, dirs in found.items():
        dirs = sorted(dirs, key=lambda d: (not os.path.basename(d).startswith(a), -os.path.getmtime(os.path.join(SRC, d))))
        out[a] = (dirs[0], None)
    return out


def main():
    os.makedirs(IMG, exist_ok=True)
    m = by_article()
    for a, v in FOLDERS.items():
        m[a] = v if isinstance(v, tuple) else (v, None)
    photos, report = {}, []
    for a in sorted(m):
        d, only = m[a]; full = os.path.join(SRC, d)
        files = [f for f in os.listdir(full) if is_img(f) and (not only or only.lower() in f.lower())]
        files.sort(key=lambda f: (rank(f, a), f.lower()))
        white = [(f, whiteness(os.path.join(full, f))) for f in files]
        first = next((f for f, w in white if w >= 0.97 and rank(f, a) < 9), None)
        if first:
            files.remove(first); files.insert(0, first)
        def fits(f):  # розмір після зменшення до MAX_SIDE
            w, h = ImageOps.exif_transpose(Image.open(os.path.join(full, f))).size
            return min(w, h) * min(1, MAX_SIDE / max(w, h)) >= MIN_SIDE
        files = [f for f in files if fits(f)]
        files = files[:MAX_PICS]
        names = []
        for i, f in enumerate(files, 1):
            im = ImageOps.exif_transpose(Image.open(os.path.join(full, f))).convert('RGB')
            im.thumbnail((MAX_SIDE, MAX_SIDE))
            fn = '%s_%d.jpg' % (a, i)
            im.save(os.path.join(IMG, fn), quality=84, optimize=True)
            names.append(fn)
        photos[a] = names
        report.append('| %s | %s | %s | %s |' % (a, d, ', '.join(files), 'так' if first else '**ні: перше фото не на білому**'))
    json.dump(photos, open(os.path.join(ROOT, 'photos.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(os.path.join(ROOT, 'photos_report.md'), 'w', encoding='utf-8') as fh:
        fh.write('# Білі фото для Розетки\n\n| Артикул | Папка | Файли (порядок у фіді) | Перше на білому |\n|---|---|---|---|\n' + '\n'.join(report) + '\n')
    print('товарів з фото: %d, без білого першого: %d' % (len(photos), sum('ні:' in r for r in report)))


if __name__ == '__main__':
    main()
