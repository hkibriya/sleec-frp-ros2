"""Small reusable FRP helper based on ReactiVex.

Context values are BehaviorSubjects. A rule trigger is a Subject.
combine_latest builds the current context, map selects the active obligation,
and with_latest_from samples it when the trigger occurs.
"""

import reactivex as rx
from reactivex import operators as ops

def build_rule_pipeline(context_subjects, context_names, trigger_stream, select_rule, execute_rule, output_stream):
    streams = [context_subjects[name] for name in context_names]

    context_stream = rx.combine_latest(*streams).pipe(
        ops.map(lambda values: dict(zip(context_names, values))),
        ops.distinct_until_changed(),
    )

    selected_obligation = context_stream.pipe(
        ops.map(select_rule),
        ops.distinct_until_changed(),
        ops.replay(buffer_size=1),
        ops.ref_count(),
    )

    def handle_trigger(values):
        event = values[0]
        obligation = values[1]
        if obligation is None:
            print(
                "Trigger received, but the rule cannot be evaluated yet "
                "because some required context is still unknown."
            )
            return None
        return execute_rule(obligation, event)

    subscription = trigger_stream.pipe(
        ops.with_latest_from(selected_obligation),
        ops.map(handle_trigger),
        ops.filter(lambda result: result is not None),
    ).subscribe(output_stream.on_next)

    return subscription

def rule_can_decide(context_subjects, context_names, select_rule):
    context = {} 
    for name in context_names:
        context[name] = context_subjects[name].value

    selected = select_rule(context)

    return selected is not None
