"""SLEEC rules used by the FRP prototype.

Each rule has a selector function, obligation functions, and an execute function.
The selectors follow ordered/nested UNLESS semantics.
"""

# S2
def select_s2(context):
    fewer_reps = context["fewer_reps"]
    if fewer_reps is False:
        return "O0"
    if fewer_reps is None:
        return None
    already_encouraged = context["already_encouraged"]
    if already_encouraged is False:
        return "O1"
    if already_encouraged is None:
        return None
    physical_issues = context["physical_issues"]
    if physical_issues is False:
        return "O2"
    if physical_issues is True:
        return "O3"
    return None


def s2_o0(event=None):
    return {"rule": "S2", "obligation": "O0", "actions": ["SHOW_NEXT_EXERCISE"], "delay_s": 60}

def s2_o1(event=None):
    return {"rule": "S2", "obligation": "O1", "actions": ["ENCOURAGE_USER"]}

def s2_o2(event=None):
    return {"rule": "S2", "obligation": "O2", "actions": ["GET_INPUT_VIA_GRAPHICAL_INTERFACE"]}

def s2_o3(event=None):
    return {"rule": "S2", "obligation": "O3", "actions": ["NOTIFY_SESSION_SUSPENDED", "ALERT_NURSE"]}

def execute_s2(obligation, event=None):
    if obligation == "O0": return s2_o0(event)
    if obligation == "O1": return s2_o1(event)
    if obligation == "O2": return s2_o2(event)
    return s2_o3(event)


# S3
def select_s3(context):
    consent = context["consent_granted"]
    authorized = context["requester_authorized"]
    # One false value is already enough to activate O1.
    if consent is False or authorized is False:
        return "O1"
    # Both must be true before O0 is certain.
    if consent is True and authorized is True:
        return "O0"
    return None

def s3_o0(event):
    data_type = str(event).strip().lower()
    return {"rule": "S3", "obligation": "O0", "actions": ["SHARE_" + data_type.upper() + "_DATA"], "detail": data_type}

def s3_o1(event):
    data_type = str(event).strip().lower()
    return {"rule": "S3", "obligation": "O1", "actions": ["DO_NOT_SHARE_DATA", "EXPLAIN_WHY"], "detail": data_type}

def execute_s3(obligation, event):
    data_type = str(event).strip().lower()
    if data_type not in ("training", "medical"):
        raise ValueError("S3 event must be 'training' or 'medical'.")
    if obligation == "O0": return s3_o0(data_type)
    return s3_o1(data_type)

# S5
def select_s5(context):
    sleeping = context["sleeping"]
    if sleeping is False:
        return "O0"
    if sleeping is None:
        return None
    rem_sleep = context["rem_sleep"]
    if rem_sleep is False:
        return "O1"
    if rem_sleep is None:
        return None
    hypoglycemia_risk = context["hypoglycemia_risk"]
    if hypoglycemia_risk is False:
        return "O2"
    if hypoglycemia_risk is True:
        return "O3"
    return None

def s5_o0(event=None):
    return {"rule": "S5", "obligation": "O0", "actions": ["REMIND_USER_TO_EAT"]}

def s5_o1(event=None):
    return {"rule": "S5", "obligation": "O1", "actions": ["GENTLY_WAKE_USER"], "deadline_s": 300, "otherwise_actions": ["ALERT_NURSE"]}

def s5_o2(event=None):
    return {"rule": "S5", "obligation": "O2", "actions": ["DO_NOT_WAKE_USER", "INFORM_NURSE"]}

def s5_o3(event=None):
    return {"rule": "S5", "obligation": "O3", "actions": ["ALERT_NURSE"]}

def execute_s5(obligation, event=None):
    if obligation == "O0": return s5_o0(event)
    if obligation == "O1": return s5_o1(event)
    if obligation == "O2": return s5_o2(event)
    return s5_o3(event)

# S6
def select_s6(context):
    c1 = context["wants_outside_diet"]
    # First hedge
    if c1 is False:
        return "O0"
    if c1 is None:
        return None
    # We reach here only if C1 is True.
    training = context["training_allows_alternative"]
    distressed = context["distressed"]
    # C2 = training OR distressed
    if training is True or distressed is True:
        return "O2"

    if training is False and distressed is False:
        return "O1"

    # C2 is still unknown.
    return None

def s6_o0(event=None):
    return {"rule": "S6", "obligation": "O0", "actions": ["DELIVER_MEAL_PORTIONS"]}

def s6_o1(event=None):
    return {"rule": "S6", "obligation": "O1", "actions": ["EXPLAIN_DIET", "DELIVER_MEAL_PORTIONS"]}

def s6_o2(event=None):
    return {"rule": "S6", "obligation": "O2", "actions": ["DELIVER_DIETARY_APPROVED_DIFFERENT_FOOD"]}

def execute_s6(obligation, event=None):
    if obligation == "O0": return s6_o0(event)
    if obligation == "O1": return s6_o1(event)
    return s6_o2(event)
