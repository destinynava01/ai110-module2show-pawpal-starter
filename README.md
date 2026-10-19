# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## Sample Output

```
Today's Schedule for Jordan
8:00 AM - Mochi: Morning walk (30 min, high priority)
8:30 AM - Luna: Breakfast (10 min, high priority)
6:00 PM - Mochi: Evening feeding (15 min, medium priority)
```

## Implementation Summary

The logic layer in `pawpal_system.py` defines four dataclasses. `Task` represents a
care activity with a description, scheduled time, duration, priority, recurrence
frequency, and completion dates. `Pet` stores pet details and its tasks, while
`Owner` manages multiple pets and combines their tasks with `get_all_tasks()`.
`Scheduler` retrieves tasks through that owner method, filters them for a selected
date and completion status, then orders them by scheduled time and priority. This
keeps scheduling across multiple pets in one place and tracks completion separately
for each occurrence. When `Scheduler.mark_task_complete()` completes a daily or
weekly task, it adds the next dated occurrence to the same pet. Run `python main.py`
to see a sample schedule.

## Testing PawPal+

Run the test suite from the project root:

```bash
python -m pytest
```

The tests cover task completion and addition, chronological sorting, filtering by
pet and completion status, daily and weekly recurrence, one-time task completion,
and same-time conflict warnings for tasks belonging to the same or different pets.

Successful test run:

```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Navad\Downloads\CodePath\AI110\Project\ai110-module2show-pawpal-starter
plugins: anyio-4.15.1
collected 9 items

tests\test_pawpal.py .........                                           [100%]

============================== 9 passed in 0.02s ==============================
```

**Confidence level:** ★★★★☆ (4/5). The core scheduling behaviors pass focused tests,
though more coverage of Streamlit interaction and unusual date/time cases would
increase confidence.

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Scheduler.sort_by_time()`, `Scheduler.get_tasks()` | `sort_by_time()` sorts tasks chronologically; `get_tasks()` filters for a date and sorts by time, then priority. |
| Filtering | `Scheduler.filter_tasks()`, `Scheduler.get_tasks()` | `filter_tasks()` can select by pet name and completion status; `get_tasks()` selects tasks due on a date and can include or exclude completed tasks. |
| Conflict detection | `Scheduler.detect_conflicts()` | Returns warning messages for pending tasks with identical scheduled timestamps on the selected date, including tasks from different pets. It does not detect overlapping durations. |
| Recurring tasks | `Task.mark_complete()`, `Scheduler.mark_task_complete()`, `Task.is_due_on()` | Completion creates a new task instance for daily tasks on the next day (`timedelta(days=1)`) or weekly tasks seven days later. The scheduler attaches it to the same pet; one-time tasks do not recur. |

## 📸 Demo Walkthrough

Describe your app in numbered steps so a reader can follow along without watching a video:

1. <!-- Describe this step -->
2. <!-- Describe this step -->
3. <!-- Describe this step -->
4. <!-- Describe this step -->
5. <!-- Add more steps as needed -->

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
