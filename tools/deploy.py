"""
Заливка фіду Розетки на Railway (server.py: віддає фід і фото, щогодини збирає фід заново).

    python tools/deploy.py            бере запушений origin/main, пакує й відправляє на Railway
    python tools/deploy.py <коміт>    те саме для конкретного коміту (повернути попередню версію)

Правила:
- Заливаємо лише з git (закомічене й запушене), не з теки на диску.
- Адресу фіду НЕ міняти: вона вписана в Pricecreator Розетки і в шапку листів SendPulse (email/).
  Проєкт, сервіс і домен створюються один раз, їхні номери лежать у tools/railway.json.
- Логін і пароль Horoshop беруться з ~/lunnitsa-site/tools/.env і кладуться в змінні сервісу (у git їх немає).

Без railway.exe (Smart App Control на цьому ПК його блокує): те саме, що `railway up`, напряму через API Railway.
Вхід — постійний ключ акаунта Railway з ~/.railway/api-token.txt. Зразок — bestiary-zoi/tools/deploy.py.
"""
import io, json, subprocess, sys, tarfile, tempfile, time, urllib.error, urllib.request, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "tools" / "railway.json"
PROJECT_NAME, SERVICE_NAME = "lunnitsa-rozetka-feed", "feed"
# що йде на сервер: код збору, правила, довідники і статичні файли (без інструментів для фото і документів)
SHIP = ["Dockerfile", "server.py", "build_feed.py", "rozetka_rules.py", "rozetka_params.py", "categories.json", "hair_types.json",
        "photos.json", "photos_sets.json", "pricecreator_params.json", "rozetka_category_params.json", "tools/check_feed.py",
        "site/img", "site/email"]
ENV_FILE = Path.home() / "lunnitsa-site" / "tools" / ".env"
SECRETS = ("HOROSHOP_DOMAIN", "HOROSHOP_LOGIN", "HOROSHOP_PASSWORD")

BACKBOARD = "https://backboard.railway.com"
API_TOKEN = Path.home() / ".railway" / "api-token.txt"   # постійний ключ акаунта; лише на цьому ПК, не в git
HEADERS = {"User-Agent": "lunnitsa-rozetka-feed-deploy", "x-source": "cli"}


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def post(url, data, headers):
    req = urllib.request.Request(url, data=data, headers={**HEADERS, **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Railway {url.split('?')[0]}: HTTP {e.code} {e.read().decode(errors='replace')[:400]}")


def gql(token, query, variables=None):
    r = post(f"{BACKBOARD}/graphql/v2", json.dumps({"query": query, "variables": variables or {}}).encode(),
             {"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    if r.get("errors"): raise SystemExit(f"Railway GraphQL: {r['errors']}")
    return r["data"]


def save(st):
    STATE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def ensure_project(token):
    """Проєкт, сервіс і середовище: створюються один раз, далі беруться з tools/railway.json."""
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    me = gql(token, "query { me { workspaces { id name projects { edges { node { id name } } } } } }")["me"]
    for w in me["workspaces"]:
        for p in w["projects"]["edges"]:
            if p["node"]["name"] == PROJECT_NAME:
                raise SystemExit(f"Проєкт {PROJECT_NAME} уже є ({p['node']['id']}), але tools/railway.json немає — перевірити вручну, щоб не створити другу адресу")
    ws = me["workspaces"][0]
    print("Створюю проєкт у", ws["name"])
    p = gql(token, "mutation($i: ProjectCreateInput!) { projectCreate(input: $i) { id environments { edges { node { id name } } } } }",
            {"i": {"name": PROJECT_NAME, "description": "Фід Розетки Lunnitsa з білими фото (замість GitHub Pages)", "workspaceId": ws["id"]}})["projectCreate"]
    env = next(e["node"]["id"] for e in p["environments"]["edges"] if e["node"]["name"] == "production")
    svc = gql(token, "mutation($i: ServiceCreateInput!) { serviceCreate(input: $i) { id } }",
              {"i": {"projectId": p["id"], "name": SERVICE_NAME}})["serviceCreate"]["id"]
    st = {"project": p["id"], "environment": env, "service": svc, "domain": None}
    save(st)
    return st


def ensure_domain(token, st):
    if not st.get("domain"):
        st["domain"] = gql(token, "mutation($i: ServiceDomainCreateInput!) { serviceDomainCreate(input: $i) { domain } }",
                           {"i": {"serviceId": st["service"], "environmentId": st["environment"], "targetPort": 8080}})["serviceDomainCreate"]["domain"]
        save(st)
    return st["domain"]


def ensure_variables(token, st, domain):
    env = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        if k.strip() in SECRETS:
            env[k.strip()] = v.strip().strip('"').strip("'")
    missing = [k for k in SECRETS if not env.get(k)]
    if missing: raise SystemExit(f"у {ENV_FILE} немає {missing}")
    env.update(PORT="8080", BASE_URL=f"https://{st.get('public_host') or domain}/")
    for name, value in env.items():
        gql(token, "mutation($i: VariableUpsertInput!) { variableUpsert(input: $i) }",
            {"i": {"projectId": st["project"], "environmentId": st["environment"], "serviceId": st["service"], "name": name, "value": value, "skipDeploys": True}})


def snapshot(ref, dst):
    sha = git("rev-parse", "--verify", f"{ref}^{{commit}}")
    if subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", sha, "origin/main"]).returncode:
        raise SystemExit(f"{ref} ще не в origin/main — спершу git push (заливаємо лише запушене)")
    z = dst.with_suffix(".zip")
    git("archive", "--format=zip", "-o", str(z), sha, *SHIP)
    with zipfile.ZipFile(z) as f: f.extractall(dst)
    return git("log", "-1", "--format=%h %s", sha)


def tarball(d):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in sorted(d.rglob("*")):
            if p.is_file(): tar.add(p, arcname="./" + p.relative_to(d).as_posix())
    return buf.getvalue()


def wait(token, dep, minutes=15):
    status = ""
    for _ in range(minutes * 6):
        status = gql(token, "query($id: String!) { deployment(id: $id) { status } }", {"id": dep})["deployment"]["status"]
        print("  стан:", status, flush=True)
        if status in ("SUCCESS", "FAILED", "CRASHED", "REMOVED", "SKIPPED"): return status
        time.sleep(10)
    return status


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ref = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    token = API_TOKEN.read_text(encoding="utf-8").strip()
    st = ensure_project(token)
    domain = ensure_domain(token, st)
    ensure_variables(token, st, domain)
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "app"
        print("Коміт:", snapshot(ref, d))
        leaked = [p for p in d.rglob("*") if p.is_file() and (p.name.startswith(".env") or p.name in ("rozetka.xml", "status.json"))]
        if leaked: raise SystemExit(f"у заливку потрапило зайве: {leaked}")
        data = tarball(d)
        print(f"Пакет: {len(data) // 1024} КБ")
        r = post(f"{BACKBOARD}/project/{st['project']}/environment/{st['environment']}/up?serviceId={st['service']}", data,
                 {"Authorization": f"Bearer {token}", "Content-Type": "application/gzip"})
    dep = r.get("deploymentId")
    print("Заливка:", dep)
    status = wait(token, dep)
    if status != "SUCCESS": raise SystemExit(f"Railway: {status}. Логи: https://railway.com/project/{st['project']}")
    print(f"Готово: https://{st.get('public_host') or domain}/rozetka.xml  (стан: /healthz)")


if __name__ == "__main__":
    main()
