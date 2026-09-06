#!/usr/bin/env python3
"""今晚吃什么 - 后端服务
菜谱数据持久化到 menus.json，API 读写，静态页面展示。
端口 8095。
"""
import http.server
import socketserver
import json
import os

PORT = 8095
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENUS_FILE = os.path.join(BASE_DIR, "menus.json")


def load_menus():
    try:
        with open(MENUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_menus(menus):
    tmp = MENUS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(menus, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MENUS_FILE)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE_DIR, **kw)

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/menus":
            return self._json(200, load_menus())
        if p == "/api/menus/count":
            return self._json(200, {"count": len(load_menus())})
        if p == "/api/health":
            return self._json(200, {"ok": True, "menus": len(load_menus())})
        # 默认静态文件
        if p == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        p = self.path.split("?")[0]
        ln = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(ln).decode("utf-8") if ln else "{}"
        if p == "/api/menus":
            # 新增或更新一套菜单
            try:
                menu = json.loads(body)
            except json.JSONDecodeError:
                return self._json(400, {"error": "bad json"})
            if not menu.get("id"):
                return self._json(400, {"error": "need id"})
            menus = load_menus()
            # 去重：同 id 覆盖
            menus = [m for m in menus if m.get("id") != menu["id"]]
            menus.append(menu)
            save_menus(menus)
            return self._json(200, {"ok": True, "count": len(menus)})
        return self._json(404, {"error": "not found"})

    def do_PUT(self):
        p = self.path.split("?")[0]
        ln = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(ln).decode("utf-8") if ln else "{}"
        if p == "/api/menus":
            # 更新菜谱的"吃过"状态
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return self._json(400, {"error": "bad json"})
            mid = data.get("id")
            eaten = data.get("eaten", False)
            if not mid:
                return self._json(400, {"error": "need id"})
            menus = load_menus()
            found = False
            for m in menus:
                if m.get("id") == mid:
                    m["eaten"] = eaten
                    found = True
                    break
            if not found:
                return self._json(404, {"error": "not found"})
            save_menus(menus)
            return self._json(200, {"ok": True, "id": mid, "eaten": eaten})
        return self._json(404, {"error": "not found"})

    def do_DELETE(self):
        p = self.path.split("?")[0]
        if p == "/api/menus":
            # ?id=xxx
            qs = self.path.split("?", 1)[1] if "?" in self.path else ""
            mid = ""
            for kv in qs.split("&"):
                if kv.startswith("id="):
                    mid = kv[3:]
            menus = load_menus()
            before = len(menus)
            menus = [m for m in menus if m.get("id") != mid]
            save_menus(menus)
            return self._json(200, {"ok": True, "removed": before - len(menus)})
        return self._json(404, {"error": "not found"})


class ThreadingServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    srv = ThreadingServer(("0.0.0.0", PORT), Handler)
    print(f"今晚吃什么 serving on 0.0.0.0:{PORT}, menus={len(load_menus())}")
    srv.serve_forever()
