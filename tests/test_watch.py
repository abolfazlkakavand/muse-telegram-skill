import fcntl
import io
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from test_telegram import tg, Base, FakeTG, msg


class Scripted(FakeTG):
    def __init__(self):
        super().__init__()
        self.script = None

    def m_getUpdates(self, b):
        if self.script is not None:
            return self.script.pop(0) if self.script else []
        return super().m_getUpdates(b)


class W(Base):
    def setUp(self):
        super().setUp()
        self.fake = Scripted()
        tg._open = self.fake.open

    def watch(self, loops=1):
        return self.run_cli("watch", "--max-loops", str(loops))

    def hb(self, age, now):
        p = tg.spath("watchman.heartbeat")
        open(p, "a").close()
        os.utime(p, (now - age, now - age))

    def put_state(self, **kw):
        with tg.state_lock():
            st = tg.load_state()
            st.update(kw)
            tg.save_state(st)


class TestWatch(W):
    def test_delivers_paired_only_and_leaves_unacked(self):
        self.pair()
        self.fake.updates += [msg(10, 111, "hello"), msg(11, 222, "spam")]
        code, res, _ = self.watch(3)
        self.assertEqual(code, 0)
        self.assertEqual((res["event"], res["count"], res["ack_upto"]), ("messages", 1, 10))
        self.assertNotIn("spam", json.dumps(res))
        self.assertTrue(os.path.exists(tg.spath("watchman.heartbeat")))
        st = tg.load_state()
        self.assertEqual(st["offset"], 12)            # Telegram is confirmed at once
        self.assertEqual(list(st["delivered"]), ["10"])  # the inbox keeps the message
        code, res, _ = self.run_cli("ack", "--upto", "10")
        self.assertEqual(res["acked"], 1)
        st = tg.load_state()
        self.assertEqual((st["offset"], st["delivered"], st["session"]["handled"]),
                         (12, {}, 1))

    def test_owner_recorded_on_pairing(self):
        self.pair()
        self.assertEqual(tg.load_state()["owners"], [111])

    def test_everything_fetched_is_confirmed_immediately(self):
        self.pair()
        self.fake.updates += [msg(5, 222, "x"), msg(6, 111, "hi"), msg(7, 222, "y")]
        self.watch()
        self.assertEqual(tg.load_state()["offset"], 8)

    def test_lease_blocks_redelivery_then_expires_then_drops(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "a"))
        self.assertEqual(self.watch()[1]["event"], "messages")
        self.assertEqual(self.watch()[1]["event"], "idle")
        base = tg.time.time()
        for i, expect in ((1, "messages"), (2, "messages")):
            with mock.patch.object(tg.time, "time", return_value=base + 1000 * i):
                self.assertEqual(self.watch()[1]["event"], expect)
        with mock.patch.object(tg.time, "time", return_value=base + 3000):
            self.assertEqual(self.watch()[1]["event"], "idle")
        self.assertTrue(any("could not process" in s["text"] for s in self.fake.sent))
        with mock.patch.object(tg.time, "time", return_value=base + 4000):
            self.assertEqual(self.watch()[1]["event"], "idle")
        self.assertEqual(tg.load_state()["delivered"], {})

    def test_send_ack_upto_only_on_success(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "q"))
        _, res, _ = self.watch()
        code, out, _ = self.run_cli("send", "--chat-id", "111", "--text", "a",
                                    "--ack-upto", str(res["ack_upto"]), "--confirm")
        self.assertEqual((code, out["ack"]["acked"]), (0, 1))
        self.assertEqual(tg.load_state()["offset"], 11)
        self.fake.updates.append(msg(12, 111, "q2"))
        self.watch()
        self.fake.fail["sendMessage"] = [(400, {"ok": False, "error_code": 400,
                                                "description": "bad"})]
        code, *_ = self.run_cli("send", "--chat-id", "111", "--text", "b",
                                "--ack-upto", "12", "--confirm")
        self.assertEqual(code, 1)
        self.assertIn("12", tg.load_state()["delivered"])

    def test_batching_collects_followups(self):
        self.pair()
        self.fake.script = [[msg(10, 111, "one")], [msg(11, 111, "two")]]
        _, res, _ = self.watch()
        self.assertEqual((res["count"], res["ack_upto"]), (2, 11))
        self.assertEqual(tg.load_state()["offset"], 12)

    def test_status_and_help_are_native(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "/status"))
        self.fake.updates.append(msg(11, 111, "/help@mybot"))
        _, res, _ = self.watch()
        self.assertEqual(res["event"], "idle")
        texts = [s["text"] for s in self.fake.sent]
        self.assertTrue(any(t.startswith("Watchman:") for t in texts))
        self.assertTrue(any(t.startswith("Owner commands") for t in texts))
        self.assertEqual(tg.load_state()["offset"], 12)

    def test_stop_is_native_and_writes_marker(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "/stop"))
        _, res, _ = self.watch(3)
        self.assertEqual(res["event"], "stopped")
        self.assertTrue(os.path.exists(tg.spath("watchman.stopped")))
        self.assertEqual(tg.decide_hook(tg.time.time(), True)["reason"], "intentionally-stopped")

    def test_non_owner_group_member_cannot_stop(self):
        self.pair(chat=-100)
        m = msg(10, -100, "/stop")
        m["message"]["from"]["id"] = 999
        self.fake.updates.append(m)
        _, res, _ = self.watch()
        self.assertEqual((res["event"], res["count"]), ("messages", 1))
        self.assertFalse(os.path.exists(tg.spath("watchman.stopped")))

    def test_new_command_goes_to_muse_and_requests_rotation(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "/new"))
        _, res, _ = self.watch()
        self.assertEqual(res["messages"][0]["owner_command"], "new")
        self.assertTrue(res["session"]["should_rotate"])

    def test_fatal_error_exits_unhealthy_without_heartbeat(self):
        self.fake.fail["getUpdates"] = [(401, {"ok": False, "error_code": 401,
                                               "description": "Unauthorized"})]
        code, res, _ = self.watch(3)
        self.assertEqual((code, res["event"]), (6, "unhealthy"))
        self.assertFalse(os.path.exists(tg.spath("watchman.heartbeat")))

    def test_repeated_errors_exit_and_recovery_resets(self):
        self.run_cli("config", "set", "max_errors", "3")
        err = (500, {"ok": False, "error_code": 500, "description": "boom"})
        self.fake.fail["getUpdates"] = [err, err]
        code, res, _ = self.watch(3)
        self.assertEqual(code, 0)
        self.assertEqual(tg._read_json_file(tg.spath("health.json"), {})["consecutive_errors"], 0)
        self.fake.fail["getUpdates"] = [err, err, err]
        code, res, _ = self.watch(5)
        self.assertEqual((code, res["consecutive_errors"]), (6, 3))

    def test_single_instance_lock(self):
        fh = open(tg.spath("watchman.lock"), "a+")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        code, _, err = self.watch()
        fh.close()
        self.assertEqual(code, 1)
        self.assertIn("already running", err["error"])

    def test_events_log_has_no_message_text(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "very secret text"))
        self.watch()
        with open(tg.spath("events.log")) as fh:
            self.assertNotIn("secret", fh.read())
        for i in range(600):
            tg.log_event("x", i=i)
        with open(tg.spath("events.log")) as fh:
            self.assertEqual(len(fh.read().splitlines()), 500)


class TestHook(W):
    NOW = 1_700_000_000.0

    def test_fresh_is_silent_and_resets_failures(self):
        self.hb(10, self.NOW)
        r = tg.decide_hook(self.NOW, False)
        self.assertEqual((r["action"], r["reason"]), ("silent", "heartbeat-fresh"))

    def test_stale_wakes_then_cooldown_then_two_failures_trip(self):
        self.hb(500, self.NOW)
        self.assertEqual(tg.decide_hook(self.NOW, False)["action"], "wake")
        self.assertEqual(tg.decide_hook(self.NOW + 60, False)["reason"], "restart-cooldown")
        self.assertEqual(tg.decide_hook(self.NOW + 200, False)["action"], "wake")
        r = tg.decide_hook(self.NOW + 400, False)
        self.assertEqual((r["action"], r["reason"]), ("disable_and_wake", "two-restart-failures"))

    def test_recovery_clears_failure_tracking(self):
        self.hb(500, self.NOW)
        tg.decide_hook(self.NOW, False)
        self.hb(5, self.NOW + 100)
        tg.decide_hook(self.NOW + 100, False)
        hs = tg._read_json_file(os.path.join(tg.spath("hook"), "state.json"), {})
        self.assertEqual((hs["failures"], hs["last_wake"]), (0, 0))
        self.hb(500, self.NOW + 1000)
        self.assertEqual(tg.decide_hook(self.NOW + 1000, False)["action"], "wake")

    def test_restart_limit_trips_breaker(self):
        os.makedirs(tg.spath("hook"), exist_ok=True)
        tg._write_json_file(os.path.join(tg.spath("hook"), "state.json"), {
            "restarts": [self.NOW - 100 * i for i in range(1, 7)],
            "failures": 0, "last_wake": 0})
        self.hb(500, self.NOW)
        r = tg.decide_hook(self.NOW, False)
        self.assertEqual((r["action"], r["reason"]), ("disable_and_wake", "circuit-breaker-limit"))

    def test_rotating_and_dry_run_and_reset(self):
        self.put_state(session={"id": "x", "started": "", "handled": 0,
                                "rotating_until": self.NOW + 100})
        self.hb(500, self.NOW)
        self.assertEqual(tg.decide_hook(self.NOW, True)["reason"], "rotating")
        self.put_state(session={"id": "x", "started": "", "handled": 0, "rotating_until": 0})
        tg.decide_hook(self.NOW, True)
        hs = tg._read_json_file(os.path.join(tg.spath("hook"), "state.json"), {})
        self.assertEqual(hs, {})
        tg.decide_hook(self.NOW, False)
        self.assertEqual(tg.decide_hook(self.NOW, False, reset=True)["action"], "reset")

    def test_cli_hook_check_prints_decision(self):
        self.hb(10, tg.time.time())
        code, res, _ = self.run_cli("hook-check", "--dry-run")
        self.assertEqual((code, res["action"]), (0, "silent"))


class TestSessionMemoryConfig(W):
    def test_ack_flags_rotation(self):
        self.run_cli("config", "set", "rotate_after", "10")
        self.put_state(session={"id": "x", "started": "", "handled": 9, "rotating_until": 0},
                       delivered={"10": {"n": 1, "until": 0}})
        _, res, _ = self.run_cli("ack", "--upto", "10")
        self.assertTrue(res["should_rotate"])

    def test_rotation_flow(self):
        self.run_cli("session", "rotate-begin")
        r = tg.decide_hook(tg.time.time(), True)
        self.assertEqual(r["reason"], "rotating")
        _, res, _ = self.run_cli("session", "rotate-end")
        self.assertEqual(res["session"]["handled"], 0)
        _, res, _ = self.run_cli("session", "handoff")
        self.assertIn("memory show", res["message"])

    def test_memory_cap_header_and_backup(self):
        with mock.patch("sys.stdin", io.StringIO("likes football")):
            self.assertEqual(self.run_cli("memory", "write")[0], 0)
        with mock.patch("sys.stdin", io.StringIO("likes football and films")):
            self.run_cli("memory", "write")
        with open(tg.spath("memory.md")) as fh:
            self.assertTrue(fh.read().startswith("<!--"))
        with open(tg.spath("memory.prev.md")) as fh:
            self.assertIn("likes football", fh.read())
        _, res, _ = self.run_cli("memory", "show")
        self.assertEqual(res["text"], "likes football and films")
        with mock.patch("sys.stdin", io.StringIO("x" * 3600)):
            code, _, err = self.run_cli("memory", "write")
        self.assertEqual(code, 2)
        self.assertIn("too long", err["error"])

    def test_config_validation(self):
        self.assertEqual(self.run_cli("config", "set", "rotate_after", "5")[0], 2)
        self.assertEqual(self.run_cli("config", "set", "ack", "loud")[0], 2)
        self.assertEqual(self.run_cli("config", "set", "nope", "1")[0], 2)
        _, res, _ = self.run_cli("config", "set", "ack", "react")
        self.assertEqual(res["config"]["ack"], "react")

    def test_stop_refuses_to_kill_foreign_pid(self):
        proc = subprocess.Popen(["sleep", "30"])
        try:
            with open(tg.spath("watchman.pid"), "w") as fh:
                fh.write(str(proc.pid))
            _, res, _ = self.run_cli("stop")
            self.assertIsNone(res["killed_pid"])
            self.assertIsNone(proc.poll())
            self.assertTrue(os.path.exists(tg.spath("watchman.stopped")))
        finally:
            proc.kill()
            proc.wait()

    def test_status_shape(self):
        self.pair()
        _, res, _ = self.run_cli("status")
        self.assertEqual(res["paired_chats"], 1)
        self.assertIn("heartbeat_age_s", res["watchman"])


if __name__ == "__main__":
    unittest.main()
