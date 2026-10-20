# -*- coding: utf-8 -*-
"""Приведення фіду до вимог Розетки (sellerhelp.rozetka.com.ua: p185 вимоги до XML, p217 назва, p212 опис, p216 фото).
Сайт lunnitsa.com не змінюється: усе це лише для фіду Розетки."""
import re

UNIT = r'(?:мл|г|шт|мм|л|кг)'
# моделі, які на сайті написані в лапках або з «№»: прибираємо розділові знаки, лишаємо назву моделі
MODEL_QUOTED = re.compile(r'[«"]([^»"]+)[»"]')
GIFT = [  # p212: в описі не можна про бонуси й подарунки; набори L017 і L304 — міцелярна вода входить у набір
    (r'\s*Іде в набір подарунком\.', ''), (r'\s*Идёт в набор подарком\.', ''),
    (r'іде в подарунок', 'теж входить у набір'), (r'идёт в подарок', 'тоже входит в набор'),
    (r'2 кроки і подарунок', '2 кроки і міцелярна вода'), (r'2 шага и подарок', '2 шага и мицеллярная вода'),
    (r'і йде в наборі подарунком до олії та гелю', 'і входить у набір разом з олією та гелем'),
    (r'и идёт в наборе подарком к маслу и гелю', 'и входит в набор вместе с маслом и гелем'),
    (r'\s*\((?:подарунок|подарок)\)', ''), (r'\s+(?:у|в) подарунок', ''), (r'\s+в подарок', ''),
]
# речення, що відсилають до карток сайту, яких на Розетці немає
SITE_REF = re.compile(r'[^.\n]*(?:в його картці|в его карточке|у картці товару|в карточке товара)[^.\n]*\.[ \t]*')
ALLOWED = {'strong', 'b', 'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'table', 'tbody', 'tr', 'td', 'th', 'div', 'span'}


def name(title, art, brand='Lunnitsa'):
    """p217: «Тип товару Бренд Модель Характеристики (Артикул)», без ком, крапок, двокрапок, тире і спецсимволів,
    без переліку складу й рекламних слів. Об'єм/вага/розмір беремо з назви сайту."""
    t = re.sub(r'\s+', ' ', title.replace('&apos;', "'").replace('ʼ', "'")).strip()
    if brand not in t:
        return t
    head, rest = t.split(brand, 1)
    head = MODEL_QUOTED.sub(r'\1', head).replace('№', '').replace(',', ' ')
    head = re.sub(r'\s+', ' ', head).strip()
    # модель — латиниця великими літерами / цифри / & у кінці частини до бренду (CLEAN SENSITIVE, EUCALYPTUS & MINT, SPF 30)
    words = head.split(' ')
    i = len(words)
    while i > 1 and re.fullmatch(r'[A-Z0-9&]+', words[i - 1]):
        i -= 1
    kind, model = ' '.join(words[:i]), ' '.join(words[i:])
    if not model and re.search(r'[«"]', t.split(brand, 1)[0]):
        q = MODEL_QUOTED.search(t.split(brand, 1)[0]).group(1)
        kind, model = re.sub(r'\s*%s\s*$' % re.escape(q), '', kind).strip(), q
    if re.fullmatch(r'\d+', model):  # олівець «№14»: номер тону
        model = 'тон %s' % model
    size = ''
    if re.match(r'(Набір|Набор)\b', kind):  # у наборах об'єм у назві сайту стосується одного засобу зі складу
        rest = ''
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*[×xх]\s*(\d+(?:[.,]\d+)?)\s*(мм|см)', rest)
    if m:
        size = '%sx%s %s' % m.groups()
    else:
        m = re.search(r'(\d+(?:[.,]\d+)?)\s*(%s)\b' % UNIT, rest)
        if m:
            size = '%s %s' % m.groups()
    out = ' '.join(x for x in (kind, brand, model, size, '(%s)' % art) if x)
    return re.sub(r'\s+', ' ', out).strip()


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def html(text):
    """p212: опис у CDATA з HTML-розміткою. Текст сайту приходить рядками: «— …» = список, «1. …» = кроки,
    короткий рядок без крапки = підзаголовок, «Питання? Відповідь.» у розділі питань = жирне питання."""
    for a, b in GIFT:
        text = re.sub(a, b, text)
    text = SITE_REF.sub('', text)
    lines = [l.strip() for l in text.replace('\r', '').split('\n') if l.strip()]
    out, lst, faq = [], None, False

    def close():
        nonlocal lst
        if lst:
            out.append('</%s>' % lst)
            lst = None
    for n, l in enumerate(lines):
        if l.startswith('— ') or l.startswith('- '):
            if lst != 'ul':
                close(); out.append('<ul>'); lst = 'ul'
            out.append('<li>%s</li>' % _esc(l[2:].strip()))
            continue
        m = re.match(r'(\d+)\.\s+(.*)', l)
        if m:
            if lst != 'ol':
                close(); out.append('<ol>'); lst = 'ol'
            out.append('<li>%s</li>' % _esc(m.group(2)))
            continue
        close()
        if n and len(l) <= 60 and not re.search(r'[.!?:;…]$', l) and n + 1 < len(lines):
            faq = bool(re.match(r'(Питання і відповіді|Вопросы и ответы)', l))
            out.append('<h3>%s</h3>' % _esc(l))
            continue
        q = re.match(r'([^?]{10,200}\?)\s+(.+)', l) if faq else None
        if q:
            out.append('<p><b>%s</b> %s</p>' % (_esc(q.group(1)), _esc(q.group(2))))
            continue
        lab = re.match(r'([^:.]{3,30}):\s+(.+)', l)
        if lab and not faq:
            out.append('<p><b>%s:</b> %s</p>' % (_esc(lab.group(1)), _esc(lab.group(2))))
            continue
        out.append('<p>%s</p>' % _esc(l))
    close()
    return ''.join(out)
