import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from test_telegram import tg, Base, FakeTG, msg
from test_watch import W

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "..", "connectors", "telegram", "hooks", "watchman-watchdog.sh")
SKILL = os.path.join(HERE, "..", "connectors", "telegram")


class TestLeaseAndCrash(W):
    def test_default_lease_is_ten_minutes(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "a"))
        base = tg.time.time()
        self.assertEqual(self.watch()[1]["event"], "messages")
        with mock.patch.object(tg.time, "time", return_value=base + 500):
            self.assertEqual(self.watch()[1]["event"], "idle")
        with mock.patch.object(tg.time, "time", return_value=base + 700):
            self.assertEqual(self.watch()[1]["event"], "messages")

    def test_lease_command_extends_for_long_jobs(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "make a file"))
        base = tg.time.time()
        self.watch()
        with mock.patch.object(tg.time, "time", return_value=base + 500):
            _, res, _ = self.run_cli("lease", "--upto", "10")
        self.assertEqual(res["extended"], 1)
        with mock.patch.object(tg.time, "time", return_value=base + 900):
            self.assertEqual(self.watch()[1]["event"], "idle")

    def test_crash_after_fetch_becomes_unhealthy_event(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "x"))
        with mock.patch.object(tg, "_apply", side_effect=RuntimeError("boom")):
            code, res, _ = self.watch()
        self.assertEqual((code, res["event"]), (6, "unhealthy"))
        self.assertIn("boom", res["error"])
        self.assertFalse(os.path.exists(tg.spath("watchman.heartbeat")))
        self.assertIn("boom", tg._read_json_file(tg.spath("health.json"), {})["last_error"])


class TestExactlyOneWake(W):
    """Regression for the live bug: a watch started before the ack woke Muse twice."""

    def get_updates_offsets(self):
        return [b["offset"] for m, b, _ in self.fake.calls if m == "getUpdates"]

    def test_new_watch_started_before_ack_does_not_redeliver(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "hello"))
        self.assertEqual(self.watch()[1]["event"], "messages")      # wake 1
        n_before = len(self.get_updates_offsets())
        code, res, _ = self.watch(3)                                  # new watch, no ack yet
        self.assertEqual((code, res["event"]), (0, "idle"))           # no wake 2
        later = self.get_updates_offsets()[n_before:]
        self.assertTrue(later and all(o > 10 for o in later))         # no busy loop on 10
        _, out, _ = self.run_cli("send", "--chat-id", "111", "--text", "hi",
                                 "--ack-upto", "10", "--confirm")
        self.assertEqual(out["ack"]["acked"], 1)
        self.assertEqual(self.watch(3)[1]["event"], "idle")           # still no wake
        self.assertEqual(len([s for s in self.fake.sent if s["text"] == "hi"]), 1)

    def test_stale_in_flight_response_after_ack_is_ignored(self):
        self.pair()
        self.fake.updates.append(msg(10, 111, "a"))
        self.watch()
        self.run_cli("ack", "--upto", "10")
        new, natives, paired = tg._apply([msg(10, 111, "a")])         # late response
        self.assertEqual((new, natives, paired), ([], [], []))
        self.assertEqual(tg.load_state()["delivered"], {})

    def test_message_survives_a_crash_between_store_and_print(self):
        self.pair()
        new, _, _ = tg._apply([msg(10, 111, "keep me")])              # stored, then "crash"
        self.assertEqual(len(new), 1)
        code, res, _ = self.watch()
        self.assertEqual((code, res["event"], res["messages"][0]["text"]),
                         (0, "messages", "keep me"))

    def test_leftovers_after_stop_are_delivered_on_next_start(self):
        self.pair()
        self.fake.script = [[msg(10, 111, "later"), msg(11, 111, "/stop")]]
        self.assertEqual(self.watch(3)[1]["event"], "stopped")
        code, res, _ = self.watch()
        self.assertEqual((res["event"], res["messages"][0]["text"]), ("messages", "later"))

    def test_legacy_delivered_entry_without_text_is_discarded(self):
        self.pair()
        self.put_state(delivered={"10": {"n": 1, "until": 0}})
        self.assertEqual(self.watch()[1]["event"], "idle")
        self.assertEqual(tg.load_state()["delivered"], {})


class TestMigrationAndHook(W):
    def test_v1_state_still_works_and_owner_falls_back_to_private_chat(self):
        tg._write_json_file(tg.spath("state.json"), {
            "version": 1, "offset": 0, "allowed_chats": [111], "pair": None,
            "seen_files": {}})
        self.fake.updates.append(msg(10, 111, "hello"))
        self.assertEqual(self.watch()[1]["event"], "messages")
        self.run_cli("ack", "--upto", "10")
        self.fake.updates.append(msg(11, 111, "/stop"))
        self.assertEqual(self.watch(3)[1]["event"], "stopped")

    def test_reset_respects_dry_run(self):
        os.makedirs(tg.spath("hook"), exist_ok=True)
        path = os.path.join(tg.spath("hook"), "state.json")
        tg._write_json_file(path, {"restarts": [1], "failures": 1, "last_wake": 0})
        self.run_cli("hook-check", "--reset", "--dry-run")
        self.assertTrue(os.path.exists(path))
        self.run_cli("hook-check", "--reset")
        self.assertFalse(os.path.exists(path))

    def test_rotate_begin_reports_watchman_state(self):
        _, res, _ = self.run_cli("session", "rotate-begin")
        self.assertFalse(res["watchman_still_running"])


class TestHookScript(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = dict(os.environ, HOME=self.tmp,
                        TELEGRAM_SKILL_HOME=os.path.join(self.tmp, "state"),
                        HATCH_HOOK_RUNTIME=os.path.join(self.tmp, "runtime.sh"))
        self.env.pop("HATCH_HOOK_DRY_RUN", None)
        os.makedirs(self.env["TELEGRAM_SKILL_HOME"])
        with open(self.env["HATCH_HOOK_RUNTIME"], "w") as fh:
            fh.write('log(){ echo "LOG $1"; }\n'
                     'silent(){ echo "SILENT $1"; exit 0; }\n'
                     'wake(){ echo "WAKE $1"; exit 0; }\n'
                     'disable_after_run(){ echo "DISABLE"; }\n')
        with open(HOOK) as fh:
            script = fh.read()
        self.script = os.path.join(self.tmp, "hook.sh")
        with open(self.script, "w") as fh:
            fh.write(script.replace("__SKILL_DIR__", os.path.abspath(SKILL)))
        self.raw = os.path.join(self.tmp, "raw.sh")
        with open(self.raw, "w") as fh:
            fh.write(script)

    def run_hook(self, path=None, **extra):
        env = dict(self.env, **extra)
        r = subprocess.run(["bash", path or self.script], env=env, capture_output=True,
                           text=True, timeout=30)
        return r.stdout.strip().splitlines()[-1], r

    def test_stale_wakes_fresh_is_silent_stop_is_silent(self):
        self.assertEqual(self.run_hook()[0], "WAKE watchman-stale")
        hb = os.path.join(self.env["TELEGRAM_SKILL_HOME"], "watchman.heartbeat")
        open(hb, "a").close()
        self.assertEqual(self.run_hook()[0], "SILENT heartbeat-fresh")
        open(os.path.join(self.env["TELEGRAM_SKILL_HOME"], "watchman.stopped"), "w").close()
        self.assertEqual(self.run_hook()[0], "SILENT intentionally-stopped")

    def test_unconfigured_hook_alerts_once_per_hour_and_always_in_dry_run(self):
        self.assertEqual(self.run_hook(self.raw)[0], "WAKE hook-not-configured")
        self.assertEqual(self.run_hook(self.raw)[0], "SILENT hook-not-configured")
        self.assertEqual(self.run_hook(self.raw, HATCH_HOOK_DRY_RUN="1")[0],
                         "WAKE hook-not-configured")

    def test_broken_skill_dir_alerts(self):
        with open(self.script) as fh:
            text = fh.read().replace(os.path.abspath(SKILL), "/nonexistent")
        bad = os.path.join(self.tmp, "bad.sh")
        with open(bad, "w") as fh:
            fh.write(text)
        self.assertEqual(self.run_hook(bad)[0], "WAKE hook-check-failed")

    def test_dry_run_does_not_record_a_restart(self):
        self.run_hook(HATCH_HOOK_DRY_RUN="1")
        self.assertFalse(os.path.exists(
            os.path.join(self.env["TELEGRAM_SKILL_HOME"], "hook", "state.json")
        ) and bool(tg._read_json_file(os.path.join(
            self.env["TELEGRAM_SKILL_HOME"], "hook", "state.json"), {}).get("restarts")))


if __name__ == "__main__":
    unittest.main()
