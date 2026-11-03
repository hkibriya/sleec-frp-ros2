"""Exhaustive tests for the SLEEC-FRP prototype.

Part 1: every rule is checked on ALL 3^n contexts (True / False / None).
The reference is independent of the selectors: each rule is written as data
(an ordered UNLESS chain), evaluated on full contexts, and the partial-context
answer is defined by completion: an obligation is expected only if every way
of filling the unknown values gives the same obligation, otherwise None.
This checks both soundness and "decides as early as possible".

Part 2: behaviour of the FRP engine (ordering of context and trigger events).

Run: python3 -m unittest -v test_exhaustive.py
"""

import itertools
import unittest

from reactivex.subject import BehaviorSubject, Subject

from frp_engine import build_rule_pipeline
from sleec_rules import (
    select_s2, select_s3, select_s5, select_s6,
    execute_s2, execute_s3, execute_s5, execute_s6,
)

# ---------------------------------------------------------------------------
# Rules as data: default obligation, then an ordered chain of (condition, obligation).
# Level k applies only if all earlier conditions held (nested UNLESS).
# ---------------------------------------------------------------------------

RULES = {
    "S2": dict(
        select=select_s2,
        names=["fewer_reps", "already_encouraged", "physical_issues"],
        default="O0",
        chain=[
            (lambda c: c["fewer_reps"], "O1"),
            (lambda c: c["already_encouraged"], "O2"),
            (lambda c: c["physical_issues"], "O3"),
        ],
    ),
    "S3": dict(
        select=select_s3,
        names=["consent_granted", "requester_authorized"],
        default="O0",
        chain=[
            (lambda c: (not c["consent_granted"]) or (not c["requester_authorized"]), "O1"),
        ],
    ),
    "S5": dict(
        select=select_s5,
        names=["sleeping", "rem_sleep", "hypoglycemia_risk"],
        default="O0",
        chain=[
            (lambda c: c["sleeping"], "O1"),
            (lambda c: c["rem_sleep"], "O2"),
            (lambda c: c["hypoglycemia_risk"], "O3"),
        ],
    ),
    "S6": dict(
        select=select_s6,
        names=["wants_outside_diet", "training_allows_alternative", "distressed"],
        default="O0",
        chain=[
            (lambda c: c["wants_outside_diet"], "O1"),
            (lambda c: c["training_allows_alternative"] or c["distressed"], "O2"),
        ],
    ),
}


def reference_full(rule, ctx):
    """Obligation for a fully known context."""
    obligation = rule["default"]
    for condition, target in rule["chain"]:
        if condition(ctx):
            obligation = target
        else:
            break
    return obligation


def reference_partial(rule, ctx):
    """Obligation for a partial context, by completion."""
    unknown = [n for n in rule["names"] if ctx[n] is None]
    outcomes = set()
    for values in itertools.product([False, True], repeat=len(unknown)):
        full = dict(ctx)
        full.update(zip(unknown, values))
        outcomes.add(reference_full(rule, full))
    return outcomes.pop() if len(outcomes) == 1 else None


class TestSelectorsExhaustive(unittest.TestCase):

    def test_all_contexts_all_rules(self):
        total = 0
        for rule_id, rule in RULES.items():
            for values in itertools.product([None, False, True], repeat=len(rule["names"])):
                ctx = dict(zip(rule["names"], values))
                expected = reference_partial(rule, ctx)
                actual = rule["select"](ctx)
                total += 1
                self.assertEqual(actual, expected, f"{rule_id} {ctx}")
        print(f"\n[exhaustive] {total} contexts checked across {len(RULES)} rules")

    def test_every_obligation_is_reachable_and_executable(self):
        executors = {"S2": execute_s2, "S3": execute_s3, "S5": execute_s5, "S6": execute_s6}
        for rule_id, rule in RULES.items():
            reached = set()
            for values in itertools.product([False, True], repeat=len(rule["names"])):
                ctx = dict(zip(rule["names"], values))
                reached.add(rule["select"](ctx))
            expected = {rule["default"]} | {t for _, t in rule["chain"]}
            self.assertEqual(reached, expected, rule_id)
            for obligation in reached:
                event = "medical" if rule_id == "S3" else None
                plan = executors[rule_id](obligation, event)
                self.assertEqual(plan["rule"], rule_id)
                self.assertEqual(plan["obligation"], obligation)
                self.assertTrue(plan["actions"])

    def test_s3_rejects_unknown_data_type(self):
        with self.assertRaises(ValueError):
            execute_s3("O0", "genetic")


# ---------------------------------------------------------------------------
# Engine behaviour
# ---------------------------------------------------------------------------

def make_s6():
    ctx = {n: BehaviorSubject(None) for n in RULES["S6"]["names"]}
    trigger, out = Subject(), Subject()
    got = []
    out.subscribe(got.append)
    build_rule_pipeline(ctx, RULES["S6"]["names"], trigger, select_s6, execute_s6, out)
    return ctx, trigger, got


class TestEngineBehaviour(unittest.TestCase):

    def test_context_then_trigger_executes(self):
        ctx, trigger, got = make_s6()
        ctx["wants_outside_diet"].on_next(False)
        trigger.on_next("USER_READY")
        self.assertEqual([p["obligation"] for p in got], ["O0"])

    def test_trigger_with_unknown_context_gives_no_output(self):
        ctx, trigger, got = make_s6()
        trigger.on_next("USER_READY")
        self.assertEqual(got, [])

    def test_late_context_does_not_replay_a_lost_trigger(self):
        # Documents current behaviour: a trigger seen while undecidable is dropped.
        ctx, trigger, got = make_s6()
        trigger.on_next("USER_READY")
        ctx["wants_outside_diet"].on_next(False)
        self.assertEqual(got, [])

    def test_latest_context_wins(self):
        ctx, trigger, got = make_s6()
        ctx["wants_outside_diet"].on_next(True)
        ctx["training_allows_alternative"].on_next(False)
        ctx["distressed"].on_next(False)
        ctx["distressed"].on_next(True)
        trigger.on_next("USER_READY")
        self.assertEqual([p["obligation"] for p in got], ["O2"])

    def test_each_trigger_executes_once(self):
        ctx, trigger, got = make_s6()
        ctx["wants_outside_diet"].on_next(False)
        trigger.on_next("USER_READY")
        trigger.on_next("USER_READY")
        self.assertEqual(len(got), 2)

    def test_context_change_alone_never_executes(self):
        ctx, trigger, got = make_s6()
        ctx["wants_outside_diet"].on_next(False)
        ctx["wants_outside_diet"].on_next(True)
        self.assertEqual(got, [])

    def test_context_can_be_retracted_to_unknown(self):
        ctx, trigger, got = make_s6()
        ctx["wants_outside_diet"].on_next(False)
        ctx["wants_outside_diet"].on_next(None)
        trigger.on_next("USER_READY")
        self.assertEqual(got, [])


if __name__ == "__main__":
    unittest.main()
