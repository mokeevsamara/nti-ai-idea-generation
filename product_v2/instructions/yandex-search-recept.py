# -*- coding: utf-8 -*-
"""Yandex Search API v2 — отчуждаемый рецепт вызова (пилот барьерной карты, 08.10.2026).

Основной поисковый механизм глубокого поиска Шага 0 (см. instructions/deep-research.md этого пакета).

Эндпоинт: https://searchapi.api.cloud.yandex.net/v2/web/search
Ключ и folderId НЕ хранятся в репозитории (публичный): только переменные окружения
YANDEX_SEARCH_API_KEY / YANDEX_FOLDER_ID.
Как получить ключ (организатору, ~10 минут):
  1. Аккаунт Yandex Cloud (console.cloud.yandex.ru), создать платёжный аккаунт
     С ПРИВЯЗАННОЙ КАРТОЙ в момент создания — иначе не будет стартового гранта
     (4 000 ₽ физлицу / 10 000 ₽ юрлицу, 60 дней; Search API грантом оплачивается).
  2. Создать каталог (folder) — его id = folder_id.
  3. В сервисе Yandex Search API подключить поиск к каталогу (постpay).
  4. Создать сервисный аккаунт → API-ключ с ролью search-api.executor.
  5. Задать окружение: YANDEX_SEARCH_API_KEY, YANDEX_FOLDER_ID.
Стоимость: ~488 ₽ за 1000 запросов вкл. НДС; прогон Шага 0 (40–60 запросов) ≈ 15–30 ₽.
Особенности вызова:
  - тело строго UTF-8 (curl из Git Bash ломает кириллицу — использовать python);
  - ответ: {"rawData": "<base64 XML>"} — декодировать;
  - между вызовами пауза ~10 с (иначе rate limit / сброс соединения);
  - searchType: SEARCH_TYPE_RU — русский поиск.
"""
import json, os, urllib.request, re, base64, time

URL = "https://searchapi.api.cloud.yandex.net/v2/web/search"


def _credentials():
    """Ключ и folderId — только из окружения (без локальных конфигов)."""
    api_key = os.getenv("YANDEX_SEARCH_API_KEY")
    folder_id = os.getenv("YANDEX_FOLDER_ID")
    if not api_key or not folder_id:
        raise RuntimeError(
            "Нет ключа: задайте YANDEX_SEARCH_API_KEY / YANDEX_FOLDER_ID "
            "в окружении (инструкция в шапке файла)"
        )
    return api_key, folder_id


def smoke_test():
    """Проверочный вызов ключа перед сбором: один дешёвый вызов. True — ключ работает."""
    try:
        return bool(ysearch("тест", n=1))
    except Exception:
        return False


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