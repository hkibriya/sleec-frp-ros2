"""ROS 2 + ReactiVex SLEEC prototype.

ROS subscriptions provide context.
ReactiVex selects obligations.
Trigger topics dispatch the selected behavior.
Actions are published symbolically.
"""

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from reactivex.subject import BehaviorSubject, Subject

from frp_engine import build_rule_pipeline, rule_can_decide

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


class SLEECRosNode(Node):

    def __init__(self):
        super().__init__("sleec_frp")

        # ------------------------------------------------------------
        # 1. Context streams
        # ------------------------------------------------------------

        names = [
            # S2
            "fewer_reps",
            "already_encouraged",
            "physical_issues",

            # S3
            "consent_granted",
            "requester_authorized",

            # S5
            "sleeping",
            "rem_sleep",
            "hypoglycemia_risk",

            # S6
            "wants_outside_diet",
            "training_allows_alternative",
            "distressed",
        ]

        self.context_streams = {}

        for name in names:
            self.context_streams[name] = BehaviorSubject(None)

        # ------------------------------------------------------------
        # 2. Trigger streams
        # ------------------------------------------------------------

        self.s2_trigger = Subject()
        self.s3_trigger = Subject()
        self.s5_trigger = Subject()
        self.s6_trigger = Subject()

        # All rule outputs come here.
        self.output = Subject()

        # Keep the FRP subscriptions.
        self.frp_subscriptions = []

        # ------------------------------------------------------------
        # 3. Build S2 pipeline
        # ------------------------------------------------------------

        self.frp_subscriptions.append(
            build_rule_pipeline(
                self.context_streams,
                [
                    "fewer_reps",
                    "already_encouraged",
                    "physical_issues",
                ],
                self.s2_trigger,
                select_s2,
                execute_s2,
                self.output,
            )
        )

        # ------------------------------------------------------------
        # 4. Build S3 pipeline
        # ------------------------------------------------------------

        self.frp_subscriptions.append(
            build_rule_pipeline(
                self.context_streams,
                [
                    "consent_granted",
                    "requester_authorized",
                ],
                self.s3_trigger,
                select_s3,
                execute_s3,
                self.output,
            )
        )

        # ------------------------------------------------------------
        # 5. Build S5 pipeline
        # ------------------------------------------------------------

        self.frp_subscriptions.append(
            build_rule_pipeline(
                self.context_streams,
                [
                    "sleeping",
                    "rem_sleep",
                    "hypoglycemia_risk",
                ],
                self.s5_trigger,
                select_s5,
                execute_s5,
                self.output,
            )
        )

        # ------------------------------------------------------------
        # 6. Build S6 pipeline
        # ------------------------------------------------------------

        self.frp_subscriptions.append(
            build_rule_pipeline(
                self.context_streams,
                [
                    "wants_outside_diet",
                    "training_allows_alternative",
                    "distressed",
                ],
                self.s6_trigger,
                select_s6,
                execute_s6,
                self.output,
            )
        )

        # ------------------------------------------------------------
        # 7. ROS output
        # ------------------------------------------------------------

        self.publisher = self.create_publisher(
            String,
            "/sleec/obligation",
            10,
        )

        self.output.subscribe(self.handle_plan)

        # ------------------------------------------------------------
        # 8. ROS context topics
        # ------------------------------------------------------------

        bool_topics = {
            # S2
            "fewer_reps": "/exercise/fewer_reps",
            "already_encouraged": "/exercise/already_encouraged",
            "physical_issues": "/exercise/physical_issues",

            # S3
            "consent_granted": "/data/consent_granted",
            "requester_authorized": "/data/requester_authorized",

            # S5
            "sleeping": "/user/sleeping",
            "rem_sleep": "/user/rem_sleep",
            "hypoglycemia_risk": "/user/hypoglycemia_risk",

            # S6
            "wants_outside_diet": "/user/wants_outside_diet",
            "training_allows_alternative":
                "/training/allows_alternative",
            "distressed": "/user/distressed",
        }

        self.ros_subscriptions = []

        # Context Listener
        for name, topic in bool_topics.items():

            sub = self.create_subscription(
                Bool,
                topic,
                lambda msg, name=name:
                    self.update_context(name, msg.data),
                10,
            )

            self.ros_subscriptions.append(sub)

        # ------------------------------------------------------------
        # 9. ROS trigger topics
        # ------------------------------------------------------------

        self.last_exercising = None
        self.last_ready = None

        # S2 trigger
        self.ros_subscriptions.append(
            self.create_subscription(
                Bool,
                "/user/exercising",
                self.on_exercising,
                10,
            )
        )

        # S5 and S6 trigger
        self.ros_subscriptions.append(
            self.create_subscription(
                Bool,
                "/user/ready",
                self.on_ready,
                10,
            )
        )

        # S3 trigger
        self.ros_subscriptions.append(
            self.create_subscription(
                String,
                "/data/request",
                self.on_data_request,
                10,
            )
        )

        # S5 WITHIN timer
        self.s5_deadline_timer = None

        self.get_logger().info(
            "SLEEC-FRP node started."
        )

    # ================================================================
    # Context Listener
    # ================================================================

    def update_context(self, name, value):

        value = bool(value)

        self.get_logger().info(
            "Context: "
            + name
            + "="
            + str(value)
        )

        # Send the new value into the corresponding BehaviorSubject.
        self.context_streams[name].on_next(value)

    # ================================================================
    # S2 trigger
    # ================================================================

    def on_exercising(self, msg):

        value = bool(msg.data)

        # Trigger S2 when the user becomes NOT exercising.
        if (
            value is False
            and (
                self.last_exercising is None
                or self.last_exercising is True
            )
        ):

            fields = [
                "fewer_reps",
                "already_encouraged",
                "physical_issues",
            ]

            if rule_can_decide(
                self.context_streams,
                fields,
                select_s2,
            ):

                self.s2_trigger.on_next(
                    "NOT_EXERCISING"
                )

            else:

                self.get_logger().warning(
                    "S2 trigger received, but the rule "
                    "cannot be evaluated yet."
                )

        self.last_exercising = value

    # ================================================================
    # S5 / S6 trigger
    # ================================================================

    def on_ready(self, msg):

        value = bool(msg.data)

        # If the user becomes ready, we treat that as successful
        # acknowledgement of S5's wake-up attempt.
        if value is True:
            self.cancel_s5_deadline()

        # Only react when the readiness state changes.
        if (
            self.last_ready is None
            or value != self.last_ready
        ):

            # --------------------------------------------------------
            # S5: user becomes NOT ready
            # --------------------------------------------------------

            if value is False:

                fields = [
                    "sleeping",
                    "rem_sleep",
                    "hypoglycemia_risk",
                ]

                if rule_can_decide(
                    self.context_streams,
                    fields,
                    select_s5,
                ):

                    self.s5_trigger.on_next(
                        "NOT_READY"
                    )

                else:

                    self.get_logger().warning(
                        "S5 trigger received, but the rule "
                        "cannot be evaluated yet."
                    )

            # --------------------------------------------------------
            # S6: user becomes ready
            # --------------------------------------------------------

            else:

                fields = [
                    "wants_outside_diet",
                    "training_allows_alternative",
                    "distressed",
                ]

                if rule_can_decide(
                    self.context_streams,
                    fields,
                    select_s6,
                ):

                    self.s6_trigger.on_next(
                        "USER_READY"
                    )

                else:

                    self.get_logger().warning(
                        "S6 trigger received, but the rule "
                        "cannot be evaluated yet."
                    )

        self.last_ready = value

    # ================================================================
    # S3 trigger
    # ================================================================

    def on_data_request(self, msg):

        data_type = msg.data.strip().lower()

        if data_type not in (
            "training",
            "medical",
        ):

            self.get_logger().warning(
                "S3 request must be "
                "'training' or 'medical'."
            )

            return

        fields = [
            "consent_granted",
            "requester_authorized",
        ]

        if rule_can_decide(
            self.context_streams,
            fields,
            select_s3,
        ):

            self.s3_trigger.on_next(
                data_type
            )

        else:

            self.get_logger().warning(
                "S3 trigger received, but the rule "
                "cannot be evaluated yet."
            )

    # ================================================================
    # Execution
    # ================================================================

    def handle_plan(self, plan):

        # ------------------------------------------------------------
        # AFTER
        # ------------------------------------------------------------

        delay_s = plan.get(
            "delay_s",
            0,
        )

        if delay_s > 0:

            self.get_logger().info(
                plan["rule"]
                + "/"
                + plan["obligation"]
                + " will run after "
                + str(delay_s)
                + " seconds."
            )

            self.one_shot_timer(
                delay_s,
                lambda:
                    self.publish_actions(
                        plan,
                        "ISSUED",
                    ),
            )

        else:

            self.publish_actions(
                plan,
                "ISSUED",
            )

        # ------------------------------------------------------------
        # WITHIN ... OTHERWISE
        # ------------------------------------------------------------

        deadline_s = plan.get(
            "deadline_s",
            0,
        )

        if deadline_s > 0:

            self.cancel_s5_deadline()

            self.s5_deadline_timer = (
                self.one_shot_timer(
                    deadline_s,
                    lambda:
                        self.publish_otherwise(
                            plan
                        ),
                )
            )

    # ================================================================
    # Publish normal actions
    # ================================================================

    def publish_actions(
        self,
        plan,
        status,
    ):

        for action in plan["actions"]:

            payload = {
                "rule": plan["rule"],
                "obligation": plan["obligation"],
                "action": action,
                "status": status,
            }

            if "detail" in plan:
                payload["detail"] = plan["detail"]

            msg = String()

            msg.data = json.dumps(
                payload
            )

            self.publisher.publish(
                msg
            )

            self.get_logger().info(
                msg.data
            )

    # ================================================================
    # Publish OTHERWISE actions
    # ================================================================

    def publish_otherwise(self, plan):

        for action in plan.get(
            "otherwise_actions",
            [],
        ):

            payload = {
                "rule": plan["rule"],
                "obligation": plan["obligation"],
                "action": action,
                "status": "OTHERWISE_TIMEOUT",
            }

            msg = String()

            msg.data = json.dumps(
                payload
            )

            self.publisher.publish(
                msg
            )

            self.get_logger().info(
                msg.data
            )

        self.s5_deadline_timer = None

    # ================================================================
    # Timer helper
    # ================================================================

    def one_shot_timer(
        self,
        seconds,
        callback,
    ):

        holder = {}

        def run_once():

            timer = holder["timer"]

            timer.cancel()

            self.destroy_timer(
                timer
            )

            callback()

        timer = self.create_timer(
            seconds,
            run_once,
        )

        holder["timer"] = timer

        return timer

    # ================================================================
    # Cancel S5 deadline
    # ================================================================

    def cancel_s5_deadline(self):

        if self.s5_deadline_timer is not None:

            self.s5_deadline_timer.cancel()

            self.destroy_timer(
                self.s5_deadline_timer
            )

            self.s5_deadline_timer = None

            self.get_logger().info(
                "S5 deadline cancelled by ready=True."
            )


# ====================================================================
# Start ROS node
# ====================================================================

def main(args=None):

    rclpy.init(
        args=args
    )

    node = SLEECRosNode()

    try:

        rclpy.spin(
            node
        )

    except KeyboardInterrupt:

        pass

    node.destroy_node()

    rclpy.shutdown()


if __name__ == "__main__":
    main()