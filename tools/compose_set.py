# -*- coding: utf-8 -*-
"""Фото набору на білому без ШІ: справжні білі пакшоти компонентів поруч на білому полотні (етикетки точні).
python tools/compose_set.py <вихід.jpg> <арт1>[:масштаб] <арт2> ...   (перше фото з photos.json; масштаб 0.4 = 40% висоти флакона)"""
import os, sys, json
from PIL import Image, ImageChops, ImageOps, ImageFilter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = json.load(open(os.path.join(ROOT, 'photos.json'), encoding='utf-8'))
S = 1600


def cut(a):
    im = ImageOps.exif_transpose(Image.open(os.path.join(ROOT, 'site', 'img', P[a][0]))).convert('RGB')
    bg = Image.new('RGB', im.size, 'white')
    box = ImageChops.difference(im, bg).convert('L').point(lambda v: 255 if v > 18 else 0).getbbox()
    return im.crop(box)


def main(out, arts):
    scale = [float(a.split(':')[1]) if ':' in a else None for a in arts]
    items = [cut(a.split(':')[0]) for a in arts]
    # висота: флакони/тюбики 100%, банки (ширші за 0.8 висоти) 55%
    H = int(S * 0.62)
    sized = []
    for im, sc in zip(items, scale):
        k = sc or (0.55 if im.width / im.height > 0.8 else 1.0)
        h = int(H * k); w = int(im.width * h / im.height); sized.append(im.resize((w, h), Image.LANCZOS))
    gap = int(S * 0.025); total = sum(i.width for i in sized) + gap * (len(sized) - 1)
    if total > S * 0.9:  # не влазить — зменшуємо все
        f = S * 0.9 / total; sized = [i.resize((int(i.width * f), int(i.height * f)), Image.LANCZOS) for i in sized]
        gap = int(gap * f); total = sum(i.width for i in sized) + gap * (len(sized) - 1)
    canvas = Image.new('RGB', (S, S), 'white'); base = int(S * 0.8); x = (S - total) // 2
    for im in sized:
        # м'яка тінь під предметом
        sh = Image.new('L', (S, S), 0); from PIL import ImageDraw
        d = ImageDraw.Draw(sh); d.ellipse((x + im.width * 0.08, base - 14, x + im.width * 0.92, base + 18), fill=70)
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        canvas = Image.composite(Image.new('RGB', (S, S), (200, 200, 200)), canvas, sh)
        layer = Image.new('RGB', (S, S), 'white'); layer.paste(im, (x, base - im.height))
        canvas = ImageChops.multiply(canvas, layer)  # білий фон пакшота зливається з полотном
        x += im.width + gap
    canvas.save(out, quality=90)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
