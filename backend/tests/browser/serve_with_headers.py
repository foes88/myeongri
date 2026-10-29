"""vercel.json 의 headers 를 그대로 붙여 web/ 을 서빙하는 로컬 서버(배포 헤더 동작 검증용). 사용: python serve_with_headers.py <dir> <port> <vercel.json>"""
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

root, port, cfgp = sys.argv[1], int(sys.argv[2]), sys.argv[3]
HEADERS = [(h["key"], h["value"]) for r in json.load(open(cfgp, encoding="utf-8")).get("headers", []) for h in r["headers"]]


class H(SimpleHTTPRequestHandler):
    def end_headers(self):
        for k, v in HEADERS:
            self.send_header(k, v)
        super().end_headers()

    def log_message(self, *a):
        pass


ThreadingHTTPServer(("127.0.0.1", port), partial(H, directory=root)).serve_forever()
