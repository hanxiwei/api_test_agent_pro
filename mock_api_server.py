from __future__ import annotations

import json
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


PETS: dict[str, dict[str, str]] = {
    "1": {"id": "1", "name": "demo-pet"},
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send_json(self, status: int, body: object) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_json(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            obj = json.loads(raw.decode("utf-8"))
        except Exception:
            return {}
        if not isinstance(obj, dict):
            return {}
        return {str(k): str(v) for k, v in obj.items()}

    def _pet_id(self) -> str | None:
        matched = re.fullmatch(r"/pets/([^/]+)", self.path)
        if not matched:
            return None
        return matched.group(1)

    def do_GET(self) -> None:
        if self.path == "/pets":
            self._send_json(200, list(PETS.values()))
            return

        pet_id = self._pet_id()
        if pet_id is not None:
            pet = PETS.get(pet_id)
            if pet is None:
                self._send_json(404, {"error": "not found"})
                return
            self._send_json(200, pet)
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/pets":
            self._send_json(404, {"error": "not found"})
            return

        data = self._read_json()
        pet_id = data.get("id") or uuid.uuid4().hex[:8]
        pet = {"id": pet_id, "name": data.get("name", "unnamed")}
        PETS[pet_id] = pet
        self._send_json(201, pet)

    def do_PUT(self) -> None:
        pet_id = self._pet_id()
        if pet_id is None:
            self._send_json(404, {"error": "not found"})
            return

        data = self._read_json()
        pet = {"id": pet_id, "name": data.get("name", "updated")}
        PETS[pet_id] = pet
        self._send_json(200, pet)

    def do_DELETE(self) -> None:
        pet_id = self._pet_id()
        if pet_id is None:
            self._send_json(404, {"error": "not found"})
            return
        PETS.pop(pet_id, None)
        self._send_empty(204)

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("Mock API server running on http://127.0.0.1:8000", flush=True)
    server.serve_forever()
