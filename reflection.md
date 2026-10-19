# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

My initial UML design had a `PetOwner` who could add pets, schedule walks, and retrieve
today's tasks. A `Pet` stored its name and species and owned its care tasks. `Task`
represented a scheduled care activity, and `Walk` inherited from `Task` for
walk-specific details. One owner could have multiple pets, and each pet could have
multiple tasks.

**b. Design changes**

The design changed to match the core system requirements more directly. I replaced
the walk-specific workflow with four general classes: `Task`, `Pet`, `Owner`, and
`Scheduler`. `Owner.get_all_tasks()` provides tasks from every pet, and the
`Scheduler` uses that method to retrieve and organize tasks across the owner's pets.
Tasks now include a description, scheduled time, duration, priority, frequency, and
completion dates. Tracking completion by date lets a recurring task be completed
today without hiding its next occurrence.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers each task's scheduled date and time, recurrence, completion
status, and priority. It returns tasks due on the selected date, excludes completed
occurrences by default, and sorts them by time with higher-priority tasks first when
times match. It also warns when pending tasks share an exact scheduled time. I
prioritized date, time, and completion so the daily list is relevant and actionable;
priority breaks ties between tasks at the same time. Pet preferences and time-budget
limits are not yet modeled, so the scheduler does not try to optimize around them.

**b. Tradeoffs**

The scheduler warns when two pending tasks have the exact same scheduled time, but
it does not currently detect tasks whose durations overlap (for example, a 30-minute
walk at 8:00 and a feeding scheduled at 8:15). Exact-time matching is a deliberate
tradeoff: it is a simple, predictable warning that catches direct conflicts across
all pets without implying that every task must be completed by one person. Since
duration is already recorded, a later version could add overlap detection if the
app needs to model the owner's availability or shared resources.

---

## 3. AI Collaboration

**a. How you used AI**

I used an AI coding assistant to refine the class design, draft the Python dataclasses,
write a runnable example, and create focused tests. Asking it to review relationships
and possible scheduling bottlenecks was especially helpful: that surfaced the need
for the scheduler to retrieve tasks through `Owner.get_all_tasks()` so tasks from
every pet are included.

**b. Judgment and verification**

The first design centered on a walk-specific workflow and treated completion like a
single status. I did not keep that approach when the requirements called for a
general-purpose scheduler and recurring tasks. I used four general classes instead,
and store completion dates so completing today's occurrence does not hide future
daily or weekly occurrences. I verified the implementation by running the sample
program and targeted tests for task completion and task addition, as well as checks
for owner-wide task retrieval, ordering, and recurrence.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
