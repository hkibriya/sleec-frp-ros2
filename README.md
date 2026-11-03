# Simple SLEEC-FRP M4 Prototype

This prototype implements SLEEC rules using **Functional Reactive Programming (FRP)** with **ReactiVex**, and connects the result to **ROS 2 Humble**.

The overall structure is inspired by CO-SLEEC. CO-SLEEC uses context-oriented programming (COP), where the current context activates a COP layer and the rule trigger dispatches the behavior associated with that layer.

In this prototype, the COP-specific mechanism is replaced by FRP:

```text
CO-SLEEC:
context -> active COP layer
trigger -> layered dispatch

This prototype:
context -> ReactiVex stream -> selected obligation
trigger -> with_latest_from -> execute selected obligation
```

The important SLEEC ideas are kept:
- each rule has a trigger;
- each rule has a default obligation `O0`;
- `UNLESS` clauses define alternative obligations;
- the current context is evaluated at runtime;
- the selected obligation is executed only when the rule trigger occurs.

---

## Project files

### `sleec_rules.py`

This file contains the actual SLEEC rule logic for **S2, S3, S5, and S6**.

For each rule, the file contains three parts:

1. A **selector function**, for example:

```python
select_s6(context)
```

The selector reads the current context and returns:

```text
"O0"
"O1"
"O2"
...
```

or:

```text
None
```

if there is not enough information yet to determine the obligation.

2. **Obligation functions**, for example:

```python
s6_o0()
s6_o1()
s6_o2()
```

These functions describe the actions associated with each SLEEC obligation.

3. An **execute function**, for example:

```python
execute_s6(obligation)
```

This calls the correct obligation function after the trigger occurs.

The selectors follow the ordered/nested SLEEC `UNLESS` semantics.

The current implementation also supports **partial context**. This means the rule does not wait for every context value if the currently known values are already enough to determine the obligation.

Example:

```text
wants_outside_diet = False
training_allows_alternative = None
distressed = None
```

For S6, this is already enough to select `O0`, because the first hedge condition is false and the later conditions are not needed.

---

### `frp_engine.py`

This file contains the reusable FRP logic based on **ReactiVex**.

Its main function is:

```python
build_rule_pipeline(...)
```

This function builds one reactive pipeline for one SLEEC rule.

The main steps are:

```text
context BehaviorSubjects
        ↓
combine_latest
        ↓
current context dictionary
        ↓
select_rule(...)
        ↓
selected obligation
        ↓
wait for trigger
        ↓
with_latest_from
        ↓
execute_rule(...)
        ↓
output stream
```

Important ReactiVex elements used here:

- `BehaviorSubject`: stores a context value and remembers its latest value.
- `Subject`: represents an event or trigger.
- `combine_latest`: combines the newest values of all context streams used by a rule.
- `map`: transforms stream values, for example from a context dictionary to an obligation.
- `distinct_until_changed`: avoids repeating the same unchanged result.
- `replay(buffer_size=1)`: remembers the latest selected obligation.
- `with_latest_from`: when the trigger occurs, gets the latest selected obligation.
- `subscribe`: receives the output of a stream.

The file also contains:

```python
rule_can_decide(...)
```

This checks whether the currently available context is already enough for the selector to return a real obligation.

It returns `True` if the selector returns `O0`, `O1`, `O2`, etc., and `False` if the selector returns `None`.

The engine also checks the selected obligation when a trigger arrives. If the obligation is still `None`, it prints a message explaining that the rule cannot yet be evaluated instead of failing silently.

---

### `frp_demo.py`

This is a small **S6 demonstration without ROS**.

It is useful for understanding the FRP logic separately from ROS.

It creates:
- three S6 context `BehaviorSubject`s;
- one `Subject` for the `USER_READY` trigger;
- one output stream.

The demo shows that:
1. context can change first;
2. the SLEEC obligation can be selected reactively;
3. no action is executed yet;
4. when `USER_READY` occurs, the latest selected obligation is executed.

It is also useful for testing partial context.

Example:

```text
wants_outside_diet = False
training_allows_alternative = None
distressed = None
```

is already enough to select S6/O0.

If the rule cannot yet be evaluated, the demo prints a message explaining that more context is required.

Run it with:

```bash
python3 frp_demo.py
```

---

### `sleec_ros.py`

This file connects the SLEEC-FRP implementation to **ROS 2**.

It contains the ROS node:

```python
SLEECRosNode
```

Its main responsibilities are:

#### 1. Create the context streams

Each context variable is represented by:

```python
BehaviorSubject(None)
```

Examples include:

```text
fewer_reps
consent_granted
sleeping
wants_outside_diet
distressed
```

`None` means that the context value has not been received yet.

#### 2. Create rule trigger streams

There is one trigger `Subject` for each rule:

```text
S2
S3
S5
S6
```

#### 3. Build the FRP pipelines

The ROS node calls:

```python
build_rule_pipeline(...)
```

for each rule.

#### 4. Listen to ROS context topics

Examples:

```text
/exercise/fewer_reps
/data/consent_granted
/user/sleeping
/user/distressed
```

When a ROS message arrives, its value is sent into the corresponding `BehaviorSubject`.

This acts as the **Context Listener** part of the architecture.

#### 5. Detect SLEEC triggers

Examples:

```text
S2: user becomes not exercising
S3: a training or medical data request arrives
S5: user becomes not ready
S6: user becomes ready
```

Before sending the trigger into the FRP pipeline, the node calls:

```python
rule_can_decide(...)
```

to check whether the current context is already sufficient.

#### 6. Execute temporal behavior

The file handles `AFTER` using a ROS one-shot timer.

For example, S2/O0 uses:

```text
AFTER 1 minute
```

The file also handles the current prototype interpretation of `WITHIN ... OTHERWISE` for S5/O1.

#### 7. Publish selected actions

The final symbolic actions are published on:

```text
/sleec/obligation
```

using `std_msgs/String`.

Example output:

```json
{
  "rule": "S6",
  "obligation": "O0",
  "action": "DELIVER_MEAL_PORTIONS",
  "status": "ISSUED"
}
```

The prototype publishes symbolic actions only. It does not control a physical robot, GUI, nurse service, or medical database.

---

### `test_rules.py`

This file contains unit tests for the SLEEC rule logic.

The tests call the selector and execute functions directly, without starting ROS.

They check:
- default obligations;
- nested `UNLESS` behavior;
- temporal metadata such as delays and deadlines;
- partial-context behavior;
- cases where the rule must return `None` because there is not enough information yet.

Run the tests with:

```bash
python3 -m unittest -v test_rules.py
```

If everything is correct, the tests should end with:

```text
OK
```

---

## How the files work together

The main flow of the complete system is:

```text
ROS context topic
        ↓
BehaviorSubject
        ↓
ReactiVex combine_latest
        ↓
SLEEC selector
        ↓
selected obligation
        ↓
wait for trigger
        ↓
with_latest_from
        ↓
execute obligation
        ↓
execution plan
        ↓
ROS output
        ↓
/sleec/obligation
```

The files are connected like this:

```text
sleec_rules.py
    defines the SLEEC rules
          ↓
frp_engine.py
    makes the rules reactive
          ↓
sleec_ros.py
    connects the reactive rules to ROS 2
```

`frp_demo.py` is a small standalone learning/demo program, while `test_rules.py` checks the rule logic automatically.

---

## Environment

This prototype currently uses:

```text
Ubuntu 22.04
ROS 2 Humble
Python 3.10
ReactiVex 5.1.0
```

Check ReactiVex:

```bash
python3 -m pip show reactivex
```

Check ROS:

```bash
echo $ROS_DISTRO
```

Expected:

```text
humble
```

---

## How to run

### 1. Run the rule tests

```bash
python3 -m unittest -v test_rules.py
```

### 2. Run the standalone FRP demo

```bash
python3 frp_demo.py
```

### 3. Run the ROS version

Terminal 1:

```bash
python3 sleec_ros.py
```

Terminal 2:

```bash
ros2 topic echo /sleec/obligation
```

Then use other terminals to publish context and trigger messages.

---

## Example: S6 with partial context

Send only the first hedge condition:

```bash
ros2 topic pub --once /user/wants_outside_diet std_msgs/msg/Bool "{data: false}"
```

Do not send values for:

```text
/training/allows_alternative
/user/distressed
```

They remain unknown.

Because `wants_outside_diet = False`, S6 can already select the default obligation `O0`.

Now trigger S6:

```bash
ros2 topic pub --once /user/ready std_msgs/msg/Bool "{data: true}"
```

Expected result:

```text
S6 / O0 / DELIVER_MEAL_PORTIONS
```

This demonstrates that the system does not wait for context values that are not required to determine the current obligation.

---

## Current prototype assumptions

- `None` means that a context value is currently unknown.
- `False` means that the condition is known and false.
- `True` means that the condition is known and true.
- A rule can execute as soon as the known context is sufficient to determine its obligation.
- If the selector returns `None`, the rule cannot yet be evaluated.
- `UNLESS` clauses are evaluated using ordered/nested SLEEC semantics.
- Rules are handled independently.
- No conflict-resolution mechanism between different SLEEC rules is currently implemented.
- Actions are symbolic ROS messages only.
- The code uses `rclpy` and ReactiVex directly and does not use the separate RxROS2 wrapper library.
