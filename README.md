# lunnitsa-rozetka-feed

**Стан: живий.** Фід Розетки для Lunnitsa з фото на білому фоні.

Адреса фіду для Розетки: https://biolabgroupcomua-boop.github.io/lunnitsa-rozetka-feed/rozetka.xml
Стан останнього збору: https://biolabgroupcomua-boop.github.io/lunnitsa-rozetka-feed/status.json

## Як працює
- GitHub Actions щогодини (`.github/workflows/feed.yml`) запускає `build_feed.py`.
- Основа — фід Розетки, який Horoshop генерує щоночі (`lunnitsa.com/marketplace-integration/rozetka-feed/`): категорії, назви, описи, ціни зі знижками.
- З API Horoshop щогодини беруться кількість і наявність. Ціни лишаються з фіду Horoshop, бо знижки наборів рахує лише він.
- Фото: `site/img`, перелік у `photos.json`. Перше фото кожного товару на білому фоні. Товари без білих фото лишаються з фото сайту (список у `status.json` → `site_photos`).
- Якщо збір не вдався, на Pages лишається попередній фід. Сайт lunnitsa.com і фото на ньому не змінюються.
- Доступ до API — секрети репо `HOROSHOP_LOGIN`, `HOROSHOP_PASSWORD`.

## Оновити фото
Фото беруться з теки дизайнера `OneDrive\DESIGNER\LUNNITSA\Сеты\MakeUp_Lunnitsa`. Після нових фото:
`python tools/make_photos.py` → перевірити `photos_report.md` → закомітити й запушити (`site/img`, `photos.json`). Товар без артикула в назві папки дописати в `FOLDERS` у `tools/make_photos.py`.

Частина коду сайту лежить у локальному репо `lunnitsa-site` (поля для Розетки: `tools/rozetka_feed.py`).
