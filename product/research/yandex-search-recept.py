# -*- coding: utf-8 -*-
"""Yandex Search API v2 — рабочий рецепт вызова (пилот барьерной карты, 08.10.2026).

Эндпоинт: https://searchapi.api.cloud.yandex.net/v2/web/search
Ключ и folderId НЕ хранятся в репозитории (публичный): берутся из окружения
YANDEX_SEARCH_API_KEY / YANDEX_FOLDER_ID либо читаются из ~/.zcode/cli/config.json
(блок mcp-сервера yandex-search).
Особенности:
  - тело строго UTF-8 (curl из Git Bash ломает кириллицу — использовать python);
  - ответ: {"rawData": "<base64 XML>"} — декодировать;
  - между вызовами пауза ~10 с (иначе rate limit / сброс соединения);
  - searchType: SEARCH_TYPE_RU — русский поиск.
"""
import json, os, urllib.request, re, base64, time

URL = "https://searchapi.api.cloud.yandex.net/v2/web/search"


def _credentials():
    """Ключ и folderId: окружение, иначе ~/.zcode/cli/config.json."""
    api_key = os.getenv("YANDEX_SEARCH_API_KEY")
    folder_id = os.getenv("YANDEX_FOLDER_ID")
    if api_key and folder_id:
        return api_key, folder_id
    cfg_path = os.path.expanduser("~/.zcode/cli/config.json")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    # блок yandex-search может лежать на разной глубине — ищем рекурсивно
    def find(d):
        if isinstance(d, dict):
            if "yandex-search" in d and isinstance(d["yandex-search"], dict):
                env = d["yandex-search"].get("env", {})
                return env.get("YANDEX_SEARCH_API_KEY"), env.get("YANDEX_FOLDER_ID")
            for v in d.values():
                r = find(v)
                if r:
                    return r
        return None
    r = find(cfg)
    if not r or not r[0]:
        raise RuntimeError("Нет ключа: задайте YANDEX_SEARCH_API_KEY/YANDEX_FOLDER_ID в окружении")
    return r


API_KEY, FOLDER_ID = _credentials()


def ysearch(query, n=5, retries=3):
    """Возвращает [(title, url), ...] выдачи Яндекса."""
    body = {
        "query": {
            "searchType": "SEARCH_TYPE_RU",
            "queryText": query,
            "familyMode": "FAMILY_MODE_NONE",
        },
        "folderId": FOLDER_ID,
        "groupSpec": {"groupsOnPage": n},
        "responseFormat": "FORMAT_XML",
    }
    err = "не пытались"
    for _ in range(retries):
        req = urllib.request.Request(
            URL,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Api-Key {API_KEY}",
            },
        )
        try:
            r = urllib.request.urlopen(req, timeout=120)
            d = json.loads(r.read().decode("utf-8"))
            xml = base64.b64decode(d["rawData"]).decode("utf-8")
            clean = lambda s: re.sub(r"</?hlword>", "", s).replace("&quot;", '"')
            titles = [clean(t) for t in re.findall(r"<title>(.*?)</title>", xml)]
            urls = re.findall(r"<url>(.*?)</url>", xml)
            return list(zip(titles, urls))
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:100]}"
            time.sleep(12)
    raise RuntimeError(err)


if __name__ == "__main__":
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else "тест"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    for t, u in ysearch(q, n):
        print(f"- {t[:100]} | {u}")
