"""Evaluation-only HTTP/SQLite service and independent checks; not an app template.

--bug injects a known defect to verify that the same checks reject it.
The header-based test identity is deliberately not production authentication.
"""

import argparse
import json
import os
import sqlite3
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def run(bug):
    checks = []
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "service.db"
        with sqlite3.connect(db_path) as db:
            db.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, owner TEXT, request_key TEXT, amount INTEGER, UNIQUE(owner, request_key))")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, status, body):
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner = self.headers.get("X-Test-User")
                if type(body.get("amount")) is not int or body["amount"] <= 0:
                    self.respond(400, {"error": "invalid amount"})
                    return
                with sqlite3.connect(db_path) as db:
                    key = body["key"]
                    if bug == "replay":
                        key += str(db.execute("SELECT COUNT(*) FROM orders").fetchone()[0])
                    db.execute("INSERT OR IGNORE INTO orders(owner,request_key,amount) VALUES (?,?,?)", (owner, key, body["amount"]))
                    order = db.execute("SELECT id FROM orders WHERE owner=? AND request_key=?", (owner, key)).fetchone()
                    if bug == "persistence":
                        db.rollback()
                self.respond(200, {"id": order[0]})

            def do_GET(self):
                with sqlite3.connect(db_path) as db:
                    row = db.execute("SELECT owner,amount FROM orders WHERE id=?", (self.path.rsplit("/", 1)[-1],)).fetchone()
                if not row or (bug != "ownership" and row[0] != self.headers.get("X-Test-User")):
                    self.respond(404, {"error": "not found"})
                else:
                    self.respond(200, {"amount": row[1]})

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = "http://127.0.0.1:" + str(server.server_port)

        def request(method, path, user, body=None):
            req = Request(url + path, data=json.dumps(body).encode() if body else None,
                          method=method, headers={"X-Test-User": user, "Content-Type": "application/json"})
            try:
                with urlopen(req, timeout=5) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                return error.code, json.load(error)

        def scenario(name, conditions):
            checks.append({"name": name, "status": "PASS" if all(conditions) else "FAIL", "executed": len(conditions)})

        try:
            status, first = request("POST", "/orders", "alice", {"amount": 10, "key": "one"})
            own_status, own = request("GET", "/orders/" + str(first["id"]), "alice")
            with sqlite3.connect(db_path) as independent:
                persisted = independent.execute("SELECT amount FROM orders WHERE id=?", (first["id"],)).fetchone()
            scenario("persistence", [status == 200, own_status == 200, own.get("amount") == 10, persisted == (10,)])
            other_status, other = request("GET", "/orders/" + str(first["id"]), "bob")
            scenario("ownership", [other_status == 404, "amount" not in other])
            replay_status, replay = request("POST", "/orders", "alice", {"amount": 10, "key": "one"})
            with sqlite3.connect(db_path) as independent:
                count = independent.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            scenario("idempotency", [replay_status == 200, replay["id"] == first["id"], count == 1])
            invalid_status, _ = request("POST", "/orders", "alice", {"amount": "banana", "key": "invalid"})
            scenario("validation", [invalid_status == 400])
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
    return {"checks": checks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bug", choices=["ownership", "replay", "persistence"])
    args = parser.parse_args()
    result = run(args.bug)
    output = os.environ.get("SUPERAGENT_REPORT")
    if output:
        Path(output).write_text(json.dumps(result), encoding="utf-8")
    else:
        print(json.dumps(result))
    raise SystemExit(1 if any(row["status"] == "FAIL" for row in result["checks"]) else 0)
