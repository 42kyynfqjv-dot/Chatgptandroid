import concurrent.futures
import secrets
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from pixel_bridge.config import Settings, relay_url
from pixel_bridge.export_openapi import export_schema
from pixel_bridge.models import OpenAppRequest
from pixel_bridge.relay import create_app
from pixel_bridge.store import Store


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = 1700000000.0
        self.settings = Settings(secrets.token_urlsafe(32), secrets.token_urlsafe(32), Path(self.directory.name) / "state.sqlite3", ttl_seconds=10)
        self.store = Store(self.settings, lambda: self.now)
        self.app = create_app(self.settings, self.store)
        self.client = TestClient(self.app, base_url="https://relay.test")
        self.addCleanup(self.client.close)
        self.operator = {"Authorization": "Bearer " + self.settings.operator_token}
        self.device = {"Authorization": "Bearer " + self.settings.device_token}

    def payload(self, key="a" * 16):
        return {"action": "open_app", "params": {"app": "clock"}, "idempotency_key": key}

    def create(self, key="a" * 16):
        response = self.client.post("/v1/actions", headers=self.operator, json=self.payload(key))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def next(self):
        response = self.client.get("/v1/device/next", headers=self.device)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["action"]

    def result(self, action_id, status="handed_off", detail="Intent dispatched"):
        return self.client.post(f"/v1/device/actions/{action_id}/result", headers=self.device, json={"status": status, "detail": detail})

    def test_roles_and_missing_auth(self):
        action = self.create()
        for method, path, body, wrong in [
            ("POST", "/v1/actions", self.payload("b" * 16), self.device),
            ("GET", "/v1/actions/" + action["id"], None, self.device),
            ("GET", "/v1/device/next", None, self.operator),
            ("POST", f"/v1/device/actions/{action['id']}/result", {"status": "rejected"}, self.operator),
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.client.request(method, path, json=body).status_code, 401)
                self.assertEqual(self.client.request(method, path, json=body, headers=wrong).status_code, 403)
        self.assertEqual(self.client.get("/v1/device/next?token=" + self.settings.device_token).status_code, 401)

    def test_https_required_and_forwarded_header_cannot_spoof_it(self):
        with TestClient(self.app, base_url="http://relay.test") as client:
            response = client.get("/v1/device/next", headers={**self.device, "X-Forwarded-Proto": "https"})
            self.assertEqual(response.status_code, 400)

    def test_action_and_auth_responses_cannot_be_cached(self):
        for headers in (self.device, {}):
            response = self.client.get("/v1/device/next", headers=headers)
            self.assertEqual(response.headers["cache-control"], "no-store")

    def test_strict_validation_allowlist_bounds_and_no_arbitrary_routing(self):
        invalid = [
            {**self.payload(), "device_id": "other"},
            {**self.payload(), "action": "shell"},
            {**self.payload(), "params": {"app": "com.any.package"}},
            {**self.payload(), "params": {"app": "browser", "url": "https://evil.invalid"}},
            {**self.payload(), "idempotency_key": "short"},
            {**self.payload(), "idempotency_key": "x" * 81},
            {**self.payload(), "idempotency_key": "has spaces in this key"},
        ]
        for hour, minute, label in [(True, 1, ""), ("2", 1, ""), (24, 1, ""), (2, -1, ""), (2, 60, ""), (2, 2, "x" * 81), (2, 2, "line\nbreak")]:
            invalid.append({"action": "set_alarm", "params": {"hour": hour, "minute": minute, "label": label}, "idempotency_key": "a" * 16})
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/v1/actions", headers=self.operator, json=payload).status_code, 422)
        self.assertIsNone(self.next())

    def test_bounded_body_and_no_reflected_payload(self):
        response = self.client.post("/v1/actions", headers=self.operator, content=b"x" * 4097)
        self.assertEqual(response.status_code, 413)
        response = self.client.post("/v1/actions", headers=self.operator, json={"private_value": "do-not-reflect"})
        self.assertNotIn("do-not-reflect", response.text)

    def test_full_lifecycle_no_completion_claim_and_terminal_result_immutable(self):
        action = self.create()
        self.assertEqual(action["status"], "queued")
        self.assertEqual(self.result(action["id"]).status_code, 409)
        claimed = self.next()
        self.assertEqual(claimed["id"], action["id"])
        self.assertEqual(claimed["status"], "awaiting_confirmation")
        self.assertIsNone(self.next())
        self.assertEqual(self.result(action["id"], "completed").status_code, 422)
        result = self.result(action["id"])
        self.assertEqual(result.json()["status"], "handed_off")
        self.assertEqual(self.result(action["id"]).json(), result.json())
        self.assertEqual(self.result(action["id"], "failed").status_code, 409)
        self.assertEqual(self.client.get("/v1/actions/" + action["id"], headers=self.operator).json(), result.json())
        self.assertIsNone(self.next())

    def test_idempotency_same_key_recovers_original_and_conflict_rejected(self):
        original = self.create()
        self.assertEqual(self.create(), original)
        changed = self.payload()
        changed["params"]["app"] = "settings"
        self.assertEqual(self.client.post("/v1/actions", headers=self.operator, json=changed).status_code, 409)
        self.next()
        self.result(original["id"], "rejected", "User declined")
        self.assertEqual(self.create()["status"], "rejected")
        self.assertIsNone(self.next())

    def test_expiry_and_lost_result_are_distinct_and_never_replayed(self):
        queued = self.create("q" * 16)
        self.now += 10
        self.assertIsNone(self.next())
        self.assertEqual(self.create("q" * 16)["status"], "expired")
        claimed = self.create("c" * 16)
        self.next()
        self.now += 10
        self.assertIsNone(self.next())
        self.assertEqual(self.create("c" * 16)["status"], "unknown")
        self.assertEqual(self.result(claimed["id"]).status_code, 409)
        self.assertEqual(self.result(queued["id"]).status_code, 409)

    def test_restart_retains_claim_and_idempotency(self):
        original = self.create()
        self.next()
        restarted = Store(self.settings, lambda: self.now)
        self.assertIsNone(restarted.claim())
        recovered = restarted.create(OpenAppRequest.model_validate(self.payload()))
        self.assertEqual(recovered.id, original["id"])
        self.assertEqual(recovered.status, "awaiting_confirmation")

    def test_late_result_conflict_keeps_unknown_terminal_across_clock_correction(self):
        action = self.create()
        self.next()
        self.now += 10
        self.assertEqual(self.result(action["id"]).status_code, 409)
        self.now -= 1
        self.assertEqual(self.store.get(action["id"]).status, "unknown")
        self.assertIsNone(self.next())

    def test_simultaneous_claim_and_create_are_atomic(self):
        request = OpenAppRequest.model_validate(self.payload())
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            created = list(pool.map(lambda _: self.store.create(request), range(16)))
            claimed = list(pool.map(lambda _: self.store.claim(), range(16)))
        self.assertEqual(len({action.id for action in created}), 1)
        self.assertEqual(sum(action is not None for action in claimed), 1)

    def test_queue_and_total_records_bounded_without_evicting_idempotency(self):
        settings = Settings(self.settings.operator_token, self.settings.device_token, self.settings.database, ttl_seconds=10, max_pending=1, max_records=2)
        with TestClient(create_app(settings, Store(settings, lambda: self.now)), base_url="https://relay.test") as client:
            self.assertEqual(client.post("/v1/actions", headers=self.operator, json=self.payload()).status_code, 200)
            self.assertEqual(client.post("/v1/actions", headers=self.operator, json=self.payload("b" * 16)).status_code, 429)
            self.now += 10
            self.assertEqual(client.post("/v1/actions", headers=self.operator, json=self.payload("b" * 16)).status_code, 200)
            self.now += 10
            self.assertEqual(client.post("/v1/actions", headers=self.operator, json=self.payload("c" * 16)).status_code, 507)
            recovered = client.post("/v1/actions", headers=self.operator, json=self.payload()).json()
            self.assertEqual(recovered["status"], "expired")

    def test_openapi_operator_only_has_confirmation_metadata(self):
        schema = export_schema("https://phone.example.invalid")
        self.assertEqual(set(schema["paths"]), {"/v1/actions", "/v1/actions/{action_id}"})
        self.assertTrue(schema["paths"]["/v1/actions"]["post"]["x-openai-isConsequential"])
        self.assertEqual(schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"], "bearer")


class ConfigTests(unittest.TestCase):
    def test_credentials_must_be_long_distinct_base64url(self):
        token = secrets.token_urlsafe(32)
        for operator, device in [("short", token), (token, token), ("x" * 42, token), ("=" * 43, token)]:
            with self.subTest(operator=operator), self.assertRaises(ValueError):
                Settings(operator, device, Path("unused"))

    def test_url_rejects_downgrade_redirect_credentials_and_caller_paths(self):
        for url in ["http://public.invalid", "https://name:password@relay.invalid", "https://relay.invalid/path", "https://relay.invalid?x=y", "file:///tmp/test"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                relay_url(url, True)
        self.assertEqual(relay_url("http://127.0.0.1:8765", True), "http://127.0.0.1:8765")
        with self.assertRaises(ValueError):
            relay_url("http://127.0.0.1:8765")
