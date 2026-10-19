from datetime import date, datetime, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


def test_mark_complete_changes_task_status() -> None:
    today = date.today()
    task = Task(
        description="Morning walk",
        scheduled_at=datetime.combine(today, datetime.min.time()),
        duration_minutes=30,
    )

    assert task.status == "pending"

    task.mark_complete()

    assert task.status == "completed"


def test_adding_task_increases_pet_task_count() -> None:
    pet = Pet(name="Mochi", species="dog")
    task = Task(
        description="Breakfast",
        scheduled_at=datetime.combine(date.today(), datetime.min.time()),
        duration_minutes=10,
    )
    initial_count = len(pet.tasks)

    pet.add_task(task)

    assert len(pet.tasks) == initial_count + 1


def test_scheduler_sorts_tasks_by_time() -> None:
    today = date.today()
    late_task = Task(
        description="Dinner",
        scheduled_at=datetime.combine(today, datetime.min.time()).replace(hour=18),
        duration_minutes=15,
    )
    early_task = Task(
        description="Breakfast",
        scheduled_at=datetime.combine(today, datetime.min.time()).replace(hour=7),
        duration_minutes=10,
    )

    assert Scheduler().sort_by_time([late_task, early_task]) == [
        early_task,
        late_task,
    ]


def test_scheduler_filters_by_pet_name_and_completion() -> None:
    today = date.today()
    owner = Owner("Jordan")
    mochi = owner.add_pet("Mochi", "dog")
    luna = owner.add_pet("Luna", "cat")
    mochi_task = Task(
        description="Walk",
        scheduled_at=datetime.combine(today, datetime.min.time()),
        duration_minutes=30,
        frequency="daily",
    )
    luna_task = Task(
        description="Feeding",
        scheduled_at=datetime.combine(today, datetime.min.time()),
        duration_minutes=10,
        frequency="daily",
    )
    mochi.add_task(mochi_task)
    luna.add_task(luna_task)
    mochi_task.mark_complete(today)

    scheduler = Scheduler()

    assert scheduler.filter_tasks(owner, today, completed=True) == [mochi_task]
    assert scheduler.filter_tasks(owner, today, completed=False) == [luna_task]
    assert scheduler.filter_tasks(owner, today, pet_name="mOcHi") == [mochi_task]


def test_completing_daily_task_adds_next_days_occurrence_to_same_pet() -> None:
    today = date.today()
    owner = Owner("Jordan")
    pet = owner.add_pet("Mochi", "dog")
    task = Task(
        description="Morning walk",
        scheduled_at=datetime.combine(today, datetime.min.time()).replace(
            hour=8, minute=30
        ),
        duration_minutes=30,
        frequency="daily",
        priority="high",
    )
    pet.add_task(task)

    next_task = Scheduler().mark_task_complete(owner, task, today)

    assert next_task is not None
    assert task.is_completed_on(today)
    assert next_task.scheduled_at == task.scheduled_at + timedelta(days=1)
    assert next_task.frequency == "daily"
    assert pet.tasks == [task, next_task]
    assert Scheduler().get_tasks(owner, today + timedelta(days=1)) == [next_task]


def test_completing_weekly_task_adds_next_weeks_occurrence() -> None:
    today = date.today()
    owner = Owner("Jordan")
    pet = owner.add_pet("Luna", "cat")
    task = Task(
        description="Grooming",
        scheduled_at=datetime.combine(today, datetime.min.time()).replace(
            hour=10
        ),
        duration_minutes=20,
        frequency="weekly",
    )
    pet.add_task(task)

    next_task = Scheduler().mark_task_complete(owner, task, today)

    assert next_task is not None
    assert next_task.scheduled_at == task.scheduled_at + timedelta(days=7)
    assert Scheduler().get_tasks(owner, today + timedelta(days=7)) == [next_task]


def test_completing_one_time_task_does_not_create_another_occurrence() -> None:
    today = date.today()
    owner = Owner("Jordan")
    pet = owner.add_pet("Mochi", "dog")
    task = Task(
        description="Vet visit",
        scheduled_at=datetime.combine(today, datetime.min.time()),
        duration_minutes=45,
    )
    pet.add_task(task)

    next_task = Scheduler().mark_task_complete(owner, task, today)

    assert next_task is None
    assert pet.tasks == [task]


def test_scheduler_warns_when_different_pets_have_tasks_at_same_time() -> None:
    today = date.today()
    owner = Owner("Jordan")
    mochi = owner.add_pet("Mochi", "dog")
    luna = owner.add_pet("Luna", "cat")
    scheduled_at = datetime.combine(today, datetime.min.time()).replace(
        hour=8, minute=0
    )
    mochi.add_task(Task("Morning walk", scheduled_at, 30))
    luna.add_task(Task("Breakfast", scheduled_at, 10))

    warnings = Scheduler().detect_conflicts(owner, today)

    assert len(warnings) == 1
    assert "8:00 AM" in warnings[0]
    assert "Mochi: Morning walk" in warnings[0]
    assert "Luna: Breakfast" in warnings[0]


def test_scheduler_warns_about_same_pet_conflicts_and_ignores_completed_tasks() -> None:
    today = date.today()
    owner = Owner("Jordan")
    pet = owner.add_pet("Mochi", "dog")
    scheduled_at = datetime.combine(today, datetime.min.time()).replace(
        hour=8, minute=0
    )
    first_task = Task("Walk", scheduled_at, 30)
    second_task = Task("Medication", scheduled_at, 5)
    pet.add_task(first_task)
    pet.add_task(second_task)

    warnings = Scheduler().detect_conflicts(owner, today)

    assert len(warnings) == 1
    assert "Mochi: Walk" in warnings[0]
    assert "Mochi: Medication" in warnings[0]

    second_task.mark_complete(today)
    assert Scheduler().detect_conflicts(owner, today) == []