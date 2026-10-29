# -*- coding: utf-8 -*-
"""Фід Розетки на Railway: віддає site/ (rozetka.xml, status.json, img/, email/) і щогодини збирає фід заново.

Збір іде в чернетку site/.build: build_feed.py пише туди rozetka.xml і status.json і сам проганяє tools/check_feed.py.
Лише якщо збір і перевірка пройшли, файли переносяться в site/ (os.replace, тож Розетка ніколи не бачить напівзаписаний файл).
Не вдалося — лишається попередній фід, помилку видно на /healthz. Після старту сервера, поки першого фіду немає, збір
повторюється кожні 5 хвилин.

Змінні: PORT, BASE_URL, HOROSHOP_DOMAIN, HOROSHOP_LOGIN, HOROSHOP_PASSWORD."""
import datetime, json, os, subprocess, sys, threading, time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, 'site')
DRAFT = os.path.join(SITE, '.build')
MINUTE = 17          # як було в GitHub Actions: о :17 щогодини
RETRY = 5 * 60       # поки немає жодного фіду
state = {'last_ok_utc': None, 'last_try_utc': None, 'last_error': None, 'fails_in_row': 0}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def build():
    state['last_try_utc'] = now()
    os.makedirs(DRAFT, exist_ok=True)
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'build_feed.py')], env={**os.environ, 'OUT_DIR': DRAFT},
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
    print(r.stdout.strip())
    if r.returncode:
        state['last_error'] = (r.stderr.strip().splitlines() or ['код %d' % r.returncode])[-1][:500]
        state['fails_in_row'] += 1
        print('ЗБІР НЕ ВДАВСЯ, лишається попередній фід:', state['last_error'])
        return False
    for f in ('rozetka.xml', 'status.json'):
        os.replace(os.path.join(DRAFT, f), os.path.join(SITE, f))
    state.update(last_ok_utc=now(), last_error=None, fails_in_row=0)
    return True


def loop():
    while True:
        try:
            ok = build()
        except Exception as e:  # таймаут чи збій мережі не мають зупиняти розклад
            state['last_error'], ok = repr(e)[:500], False
            state['fails_in_row'] += 1
            print('ЗБІР НЕ ВДАВСЯ:', state['last_error'])
        if not ok and not os.path.exists(os.path.join(SITE, 'rozetka.xml')):
            time.sleep(RETRY)
            continue
        t = time.time()
        nxt = (t // 3600) * 3600 + MINUTE * 60
        if nxt <= t + 60:
            nxt += 3600
        time.sleep(nxt - t)


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.xml': 'application/xml; charset=utf-8',
                      '.json': 'application/json; charset=utf-8'}

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/healthz':
            ok = os.path.exists(os.path.join(SITE, 'rozetka.xml'))
            body = json.dumps({'feed': ok, **state}, ensure_ascii=False).encode('utf-8')
            self.send_response(200 if ok else 503)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith('/.') or '/.' in path or path == '/':
            self.send_error(404)
            return
        super().do_GET()

    def end_headers(self):
        if self.path.split('?', 1)[0].endswith(('.xml', '.json')):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404)

    def log_message(self, fmt, *args):
        pass  # Розетка і Pricecreator ходять часто: у логах лише збори


if __name__ == '__main__':
    threading.Thread(target=loop, daemon=True).start()
    port = int(os.environ.get('PORT', '8080'))
    print('Фід Розетки слухає порт', port)
    ThreadingHTTPServer(('', port), partial(Handler, directory=SITE)).serve_forever()
