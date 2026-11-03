"""Small S6 demo that runs ReactiVex without ROS.
Run: python3 frp_demo.py
"""
from reactivex.subject import BehaviorSubject, Subject
from frp_engine import build_rule_pipeline
from sleec_rules import select_s6, execute_s6

context = {
    "wants_outside_diet": BehaviorSubject(None),
    "training_allows_alternative": BehaviorSubject(None),
    "distressed": BehaviorSubject(None),
}
user_ready = Subject()
output = Subject()
output.subscribe(lambda plan: print("OUTPUT:", plan))

subscription = build_rule_pipeline(
    context_subjects=context,
    context_names=[
        "wants_outside_diet",
        "training_allows_alternative",
        "distressed",
    ],
    trigger_stream=user_ready,
    select_rule=select_s6,
    execute_rule=execute_s6,
    output_stream=output,
)

print("Updating context...")
# context["wants_outside_diet"].on_next(True)
context["wants_outside_diet"].on_next(False)

print("Rule context evaluated.")
print("User becomes ready:")
user_ready.on_next("USER_READY")
