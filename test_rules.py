"""Tests for the SLEEC rule functions."""

import unittest

from sleec_rules import (
    select_s2,
    execute_s2,
    select_s3,
    execute_s3,
    select_s5,
    execute_s5,
    select_s6,
    execute_s6,
)


class TestRules(unittest.TestCase):

    # ------------------------------------------------------------
    # S2
    # ------------------------------------------------------------

    def test_s2_default_obligation(self):
        context = {
            "fewer_reps": False,
            "already_encouraged": None,
            "physical_issues": None,
        }

        obligation = select_s2(context)

        self.assertEqual(obligation, "O0")

        plan = execute_s2(obligation)

        self.assertEqual(plan["delay_s"], 60)
        self.assertEqual(
            plan["actions"],
            ["SHOW_NEXT_EXERCISE"]
        )


    def test_s2_not_enough_context(self):
        context = {
            "fewer_reps": True,
            "already_encouraged": None,
            "physical_issues": None,
        }

        obligation = select_s2(context)

        self.assertEqual(obligation, None)


    def test_s2_nested_obligation(self):
        context = {
            "fewer_reps": True,
            "already_encouraged": True,
            "physical_issues": False,
        }

        obligation = select_s2(context)

        self.assertEqual(obligation, "O2")


    # ------------------------------------------------------------
    # S3
    # ------------------------------------------------------------

    def test_s3_blocked_without_consent(self):
        context = {
            "consent_granted": False,
            "requester_authorized": None,
        }

        obligation = select_s3(context)

        self.assertEqual(obligation, "O1")

        plan = execute_s3(
            obligation,
            "medical"
        )

        self.assertEqual(
            plan["obligation"],
            "O1"
        )


    def test_s3_default_share(self):
        context = {
            "consent_granted": True,
            "requester_authorized": True,
        }

        obligation = select_s3(context)

        self.assertEqual(obligation, "O0")

        plan = execute_s3(
            obligation,
            "training"
        )

        self.assertEqual(
            plan["actions"],
            ["SHARE_TRAINING_DATA"]
        )


    def test_s3_not_enough_context(self):
        context = {
            "consent_granted": True,
            "requester_authorized": None,
        }

        obligation = select_s3(context)

        self.assertEqual(obligation, None)


    # ------------------------------------------------------------
    # S5
    # ------------------------------------------------------------

    def test_s5_default_obligation(self):
        context = {
            "sleeping": False,
            "rem_sleep": None,
            "hypoglycemia_risk": None,
        }

        obligation = select_s5(context)

        self.assertEqual(obligation, "O0")


    def test_s5_nested_obligation(self):
        context = {
            "sleeping": True,
            "rem_sleep": False,
            "hypoglycemia_risk": None,
        }

        obligation = select_s5(context)

        self.assertEqual(obligation, "O1")

        plan = execute_s5(obligation)

        self.assertEqual(
            plan["deadline_s"],
            300
        )

        self.assertEqual(
            plan["otherwise_actions"],
            ["ALERT_NURSE"]
        )


    def test_s5_not_enough_context(self):
        context = {
            "sleeping": True,
            "rem_sleep": True,
            "hypoglycemia_risk": None,
        }

        obligation = select_s5(context)

        self.assertEqual(obligation, None)


    # ------------------------------------------------------------
    # S6
    # ------------------------------------------------------------

    def test_s6_default_with_partial_context(self):
        context = {
            "wants_outside_diet": False,
            "training_allows_alternative": None,
            "distressed": None,
        }

        obligation = select_s6(context)

        self.assertEqual(obligation, "O0")

        plan = execute_s6(obligation)

        self.assertEqual(
            plan["actions"],
            ["DELIVER_MEAL_PORTIONS"]
        )


    def test_s6_not_enough_context(self):
        context = {
            "wants_outside_diet": True,
            "training_allows_alternative": None,
            "distressed": None,
        }

        obligation = select_s6(context)

        self.assertEqual(obligation, None)


    def test_s6_o1(self):
        context = {
            "wants_outside_diet": True,
            "training_allows_alternative": False,
            "distressed": False,
        }

        obligation = select_s6(context)

        self.assertEqual(obligation, "O1")

        plan = execute_s6(obligation)

        self.assertEqual(
            plan["actions"],
            [
                "EXPLAIN_DIET",
                "DELIVER_MEAL_PORTIONS"
            ]
        )


    def test_s6_o2_with_partial_context(self):
        context = {
            "wants_outside_diet": True,
            "training_allows_alternative": True,
            "distressed": None,
        }

        obligation = select_s6(context)

        self.assertEqual(obligation, "O2")

        plan = execute_s6(obligation)

        self.assertEqual(
            plan["actions"],
            [
                "DELIVER_DIETARY_APPROVED_DIFFERENT_FOOD"
            ]
        )


if __name__ == "__main__":
    unittest.main()