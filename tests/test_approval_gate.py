"""Live writes sent by connector_executor.py fire only against a matching,
approved, unexpired, unused approval record.

Hermes review (NousResearch/hermes-agent#132571, item 2) found writes gated by
a plain `--confirm` flag the model can set, approval records stamped
`approved_by="user"` for any caller, and 23 of 24 skill calls passing fields the
approval step rejects. The user chose code enforcement (2026-10-10), with the
red-team's limits stated honestly: code cannot tell the user from the model, so
a record proves only that the approval step ran for this exact request, once,
inside its window. These tests plant every way around that the red-team named
and require each to send nothing.

The request is the real Slack `internal-kickoff` write, built through the real
resolver; only the network (urlopen) and the MCP config are mocked.

Stdlib only.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import SCRIPTS_DIR, import_script  # noqa: E402

sys.path.insert(0, str(SCRIPTS_DIR))
import _common  # noqa: E402
import connector_executor as ce  # noqa: E402
import connector_resolver as cr  # noqa: E402

BRAND = "acme"
TOKEN = "xoxb-test-token-123"
ENV = {"SLACK_BOT_TOKEN": TOKEN, "UNRELATED_SECRET": "must-not-leak"}
PLAN = {"plan": {"slack_channel": "#launch", "kickoff_message": "Launch is go", "kickoff_blocks": "none"}}


class _Resp:
    status = 200

    def read(self):
        return json.dumps({"ok": True, "ts": "1.2"}).encode()

    def close(self):
        pass


class GateCase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        (self.home / "brands" / BRAND).mkdir(parents=True)
        (self.home / "brands" / "other").mkdir(parents=True)
        self._env = mock.patch.dict(os.environ, {"CLAUDE_MARKETING_HOME": str(self.home)})
        self._env.start()
        self._mcp = mock.patch.object(cr, "_load_mcp_json", return_value={"slack": {}})
        self._mcp.start()
        # Point the resolver's import-time constant at the temp workspace too, so code
        # that still used it would write HERE (and the side-effect tests can see it).
        mock.patch.object(cr, "BRANDS_DIR", self.home / "brands").start()
        self.urlopen = mock.patch.object(ce.urllib.request, "urlopen", return_value=_Resp()).start()
        self.am = import_script("approval-manager.py", "approval_manager_gate_test")

    def tearDown(self):
        mock.patch.stopall()
        shutil.rmtree(self.home, ignore_errors=True)

    def run_exec(self, approval_id=None, data=PLAN, brand=BRAND, action="internal-kickoff", **kw):
        return ce.execute_action(action, brand, execute=True, env=dict(ENV), data=data,
                                 approval_id=approval_id, log_to_tracker=True, **kw)

    def prepare_and_approve(self, data=PLAN):
        prep = self.run_exec(data=data)
        self.assertTrue(prep["approval_required"], prep)
        self.assertFalse(prep["execute_attempted"])
        res = self.am.approve(BRAND, prep["approval_id"])
        self.assertEqual(res.get("status"), "approved", res)
        return prep["approval_id"]

    def record(self, approval_id):
        return json.loads((self.home / "brands" / BRAND / "approvals" / f"{approval_id}.json").read_text())

    def assert_nothing_sent(self, result):
        self.urlopen.assert_not_called()
        self.assertFalse(result.get("execute_attempted"), result)


class TestPrepareApproveFire(GateCase):
    def test_execute_without_id_prepares_a_pending_record_and_sends_nothing(self):
        prep = self.run_exec()
        self.assert_nothing_sent(prep)
        rec = self.record(prep["approval_id"])
        self.assertEqual(rec["status"], "pending")
        self.assertEqual(rec["payload_hash"], prep["approval_payload_hash"])
        preview = prep["preview"]
        self.assertEqual(preview["url"], "https://slack.com/api/chat.postMessage")
        self.assertEqual(preview["body"]["channel"], "#launch")
        self.assertEqual(preview["credential_env"], "SLACK_BOT_TOKEN")
        self.assertNotIn(TOKEN, json.dumps(prep), "the credential value leaked into the preview")
        self.assertTrue(any("approve --id" in s for s in prep["next_steps"]))

    def test_approved_record_fires_once_and_is_logged_with_the_record(self):
        aid = self.prepare_and_approve()
        res = self.run_exec(approval_id=aid)
        self.assertTrue(res["execute_attempted"])
        self.assertEqual(self.urlopen.call_count, 1)
        self.assertEqual(self.record(aid)["status"], "executed")
        self.assertEqual(self.record(aid).get("approved_via"), "approval-step")
        self.assertNotIn("approved_by", self.record(aid))
        logs = list((self.home / "brands" / BRAND / "executions").glob("*.json"))
        self.assertEqual(len(logs), 1)
        entry = json.loads(logs[0].read_text())
        self.assertEqual(entry["approval_record"]["approval_id"], aid)
        self.assertEqual(entry["payload_hash"], self.record(aid)["payload_hash"])


class TestPlantedBypassesSendNothing(GateCase):
    def test_no_id_is_not_enough_even_with_confirm(self):
        res = ce.execute_action("internal-kickoff", BRAND, execute=True, confirm=True, env=dict(ENV),
                                data=PLAN, log_to_tracker=False)
        self.assert_nothing_sent(res)

    def test_pending_record_cannot_fire(self):
        prep = self.run_exec()
        res = self.run_exec(approval_id=prep["approval_id"])
        self.assert_nothing_sent(res)
        self.assertIn("pending", res["execute_blocked_reason"])

    def test_payload_changed_after_approval_is_refused(self):
        aid = self.prepare_and_approve()
        changed = {"plan": dict(PLAN["plan"], kickoff_message="Launch is go!")}  # one byte
        res = self.run_exec(approval_id=aid, data=changed)
        self.assert_nothing_sent(res)
        self.assertIn("hash mismatch", res["execute_blocked_reason"])
        self.assertEqual(self.record(aid)["status"], "approved", "a refused fire must not consume the record")

    def test_reused_record_is_refused(self):
        aid = self.prepare_and_approve()
        self.run_exec(approval_id=aid)
        self.urlopen.reset_mock()
        res = self.run_exec(approval_id=aid)
        self.assert_nothing_sent(res)
        self.assertIn("already used", res["execute_blocked_reason"])

    def test_expired_fire_window_is_refused(self):
        aid = self.prepare_and_approve()
        path = self.home / "brands" / BRAND / "approvals" / f"{aid}.json"
        rec = json.loads(path.read_text())
        rec["fire_expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        path.write_text(json.dumps(rec))
        res = self.run_exec(approval_id=aid)
        self.assert_nothing_sent(res)
        self.assertIn("expired", res["execute_blocked_reason"])

    def test_unreviewed_record_expires(self):
        prep = self.run_exec()
        path = self.home / "brands" / BRAND / "approvals" / f"{prep['approval_id']}.json"
        rec = json.loads(path.read_text())
        rec["pending_expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        path.write_text(json.dumps(rec))
        self.assertIn("error", self.am.approve(BRAND, prep["approval_id"]))

    def test_record_from_another_brand_is_refused(self):
        aid = self.prepare_and_approve()
        res = self.run_exec(approval_id=aid, brand="other")
        self.assert_nothing_sent(res)

    def test_hand_edited_record_for_another_request_is_refused(self):
        aid = self.prepare_and_approve()
        path = self.home / "brands" / BRAND / "approvals" / f"{aid}.json"
        rec = json.loads(path.read_text())
        rec["payload_hash"] = "0" * 64
        path.write_text(json.dumps(rec))
        res = self.run_exec(approval_id=aid)
        self.assert_nothing_sent(res)

    def test_network_error_before_send_releases_the_record(self):
        aid = self.prepare_and_approve()
        self.urlopen.side_effect = ce.urllib.error.URLError("dns failure")
        res = self.run_exec(approval_id=aid)
        self.assertEqual(res["execution"]["status"], "network_error")
        self.assertEqual(self.record(aid)["status"], "approved", "nothing was sent, so the record is released")

    def test_http_error_still_consumes(self):
        aid = self.prepare_and_approve()
        err = ce.urllib.error.HTTPError("https://slack.com", 500, "boom", {}, None)
        err.read = lambda: b"{}"
        self.urlopen.side_effect = err
        self.run_exec(approval_id=aid)
        self.assertEqual(self.record(aid)["status"], "failed", "the platform saw it, so the record is consumed")


class TestBatchAndStanding(GateCase):
    def _plan_file(self, items):
        p = self.home / "plan.json"
        p.write_text(json.dumps(items))
        return p

    def test_batch_one_record_items_consumed_one_by_one(self):
        a = {"action": "internal-kickoff", "data": PLAN}
        b = {"action": "internal-kickoff", "data": {"plan": dict(PLAN["plan"], slack_channel="#ops")}}
        batch = ce.prepare_batch(BRAND, [a, b], env=dict(ENV))
        self.assertEqual(batch["status"], "prepared", batch)
        self.urlopen.assert_not_called()
        self.assertEqual(len(batch["items"]), 2)
        self.am.approve(BRAND, batch["approval_id"])
        r1 = self.run_exec(approval_id=batch["approval_id"], data=a["data"])
        self.assertTrue(r1["execute_attempted"])
        again = self.run_exec(approval_id=batch["approval_id"], data=a["data"])
        self.assertFalse(again["execute_attempted"])
        self.assertIn("already sent", again["execute_blocked_reason"])
        changed = self.run_exec(approval_id=batch["approval_id"],
                                data={"plan": dict(PLAN["plan"], slack_channel="#all-hands")})
        self.assertFalse(changed["execute_attempted"])
        r2 = self.run_exec(approval_id=batch["approval_id"], data=b["data"])
        self.assertTrue(r2["execute_attempted"])
        self.assertEqual(self.urlopen.call_count, 2)
        self.assertEqual(self.record(batch["approval_id"])["status"], "consumed")

    def test_standing_approval_is_scoped_and_capped(self):
        made = self.am.create_standing(BRAND, {"kind": "executor", "connector": "slack",
                                               "actions": ["internal-kickoff"], "max_uses_per_day": 2,
                                               "days": 7, "summary": "launch pings"})
        sid = made["approval_id"]
        self.assertFalse(self.run_exec(approval_id=sid)["execute_attempted"], "unapproved standing record fired")
        self.am.approve(BRAND, sid)
        self.assertTrue(self.run_exec(approval_id=sid)["execute_attempted"])
        self.assertTrue(self.run_exec(approval_id=sid)["execute_attempted"])
        capped = self.run_exec(approval_id=sid)
        self.assertFalse(capped["execute_attempted"])
        self.assertIn("cap", capped["execute_blocked_reason"])
        self.assertEqual(len(self.record(sid)["uses"]), 2)

    def test_standing_limits_are_bounded(self):
        for bad in ({"days": 8}, {"max_uses_per_day": 0}, {"actions": []}, {"kind": "anything"}):
            data = {"kind": "executor", "actions": ["internal-kickoff"], "max_uses_per_day": 2, "days": 7,
                    "summary": "x"}
            data.update(bad)
            with self.subTest(bad=bad):
                self.assertIn("error", self.am.create_standing(BRAND, data))


class TestAutopilotStandingApproval(GateCase):
    """allowed_actions defaults to []; pre-authorising needs an approved, bounded
    autopilot standing approval, and automatic corrections stop at its cap."""

    def setUp(self):
        super().setUp()
        self.chm = import_script("campaign-health-monitor.py", "chm_gate_test")

    def test_default_is_propose_everything(self):
        self.assertEqual(self.chm.get_guardrails(BRAND)["allowed_actions"], [])

    def test_pre_authorising_needs_a_covering_standing_approval(self):
        self.assertIn("error", self.chm.set_guardrails(BRAND, {"allowed_actions": ["adjust_bid"]}))
        narrow = self.am.create_standing(BRAND, {"kind": "autopilot", "actions": ["pause_ad_set"],
                                                 "max_uses_per_day": 2, "days": 30, "summary": "pauses only"})
        self.am.approve(BRAND, narrow["approval_id"])
        res = self.chm.set_guardrails(BRAND, {"allowed_actions": ["adjust_bid"]}, approval_id=narrow["approval_id"])
        self.assertIn("does not cover", res.get("error", ""))
        executor_kind = self.am.create_standing(BRAND, {"kind": "executor", "actions": ["adjust_bid"],
                                                        "max_uses_per_day": 2, "days": 7, "summary": "x"})
        self.am.approve(BRAND, executor_kind["approval_id"])
        res = self.chm.set_guardrails(BRAND, {"allowed_actions": ["adjust_bid"]},
                                      approval_id=executor_kind["approval_id"])
        self.assertIn("not an autopilot", res.get("error", ""))

    def test_cap_stops_automatic_corrections(self):
        st = self.am.create_standing(BRAND, {"kind": "autopilot", "actions": ["adjust_bid"],
                                             "max_uses_per_day": 1, "days": 30, "summary": "bid trims"})
        self.am.approve(BRAND, st["approval_id"])
        saved = self.chm.set_guardrails(BRAND, {"allowed_actions": ["adjust_bid"]}, approval_id=st["approval_id"])
        self.assertEqual(saved.get("status"), "saved", saved)
        first = self.chm.log_correction(BRAND, "c1", "cpc spike", "bid -10%", True, "cpc down")
        self.assertEqual(first.get("status"), "logged", first)
        second = self.chm.log_correction(BRAND, "c1", "cpc spike", "bid -10%", True, "cpc down")
        self.assertTrue(second.get("cap_reached"), second)
        manual = self.chm.log_correction(BRAND, "c1", "cpc spike", "bid -10%", False, "cpc down")
        self.assertEqual(manual.get("status"), "logged", "a correction the user approved is not capped")

    def test_existing_configs_keep_working(self):
        cfg = self.home / "brands" / BRAND / "config"
        cfg.mkdir(parents=True)
        (cfg / "guardrails.json").write_text(json.dumps({"allowed_actions": ["pause_ad_set"]}))
        self.assertEqual(self.chm.get_guardrails(BRAND)["allowed_actions"], ["pause_ad_set"])


class TestNoSideEffectBeforeTheGate(GateCase):
    """Red-team L4: resolve_action ran arm-watchdog (a local write) during
    resolution, so even a dry run had a side effect before any gate."""

    def test_dry_run_of_a_local_action_writes_nothing(self):
        ce.execute_action("arm-watchdog", BRAND, execute=False, env=dict(ENV), log_to_tracker=False)
        self.assertFalse((self.home / "brands" / BRAND / "watchdogs").exists(),
                         "a dry run created watchdog files")

    def test_dry_run_of_a_write_sends_nothing_and_records_nothing(self):
        res = ce.execute_action("internal-kickoff", BRAND, execute=False, env=dict(ENV), data=PLAN,
                                log_to_tracker=False)
        self.urlopen.assert_not_called()
        self.assertFalse((self.home / "brands" / BRAND / "approvals").exists())
        self.assertEqual(res["mode"], "manifest_ready")

    def test_local_action_runs_only_under_execute(self):
        ce.execute_action("arm-watchdog", BRAND, execute=True, env=dict(ENV), log_to_tracker=False)
        self.assertTrue((self.home / "brands" / BRAND / "watchdogs").exists())

    def test_only_the_connectors_own_variables_are_substituted(self):
        scoped = ce._scoped_env(dict(ENV, SLACK_SIGNING_SECRET="s"), "slack")
        self.assertEqual(set(scoped), {"SLACK_BOT_TOKEN", "SLACK_SIGNING_SECRET"})
        self.assertNotIn("UNRELATED_SECRET", scoped)
        spec = ce._substitute_env({"url": "https://x/{UNRELATED_SECRET}"}, scoped)
        self.assertEqual(spec["url"], "https://x/{UNRELATED_SECRET}")


if __name__ == "__main__":
    unittest.main()
