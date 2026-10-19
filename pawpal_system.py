from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal


Frequency = Literal["once", "daily", "weekly"]
Priority = Literal["low", "medium", "high"]


@dataclass
class Task:
    description: str
    scheduled_at: datetime
    duration_minutes: int
    frequency: Frequency = "once"
    priority: Priority = "medium"
    completed_dates: set[date] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Validate task duration, recurrence frequency, and priority."""
        if self.duration_minutes <= 0:
            raise ValueError("Task duration must be greater than zero.")
        if self.frequency not in ("once", "daily", "weekly"):
            raise ValueError("Frequency must be once, daily, or weekly.")
        if self.priority not in ("low", "medium", "high"):
            raise ValueError("Priority must be low, medium, or high.")

    def is_due_on(self, day: date) -> bool:
        """Return whether this task occurrence is scheduled for the given date."""
        return self.scheduled_at.date() == day

    def is_completed_on(self, day: date) -> bool:
        """Return whether this task's occurrence is complete on the given date."""
        return day in self.completed_dates

    @property
    def status(self) -> str:
        """Return this task's completion status for today."""
        return "completed" if self.is_completed_on(date.today()) else "pending"

    def mark_complete(self, day: date | None = None) -> Task | None:
        """Complete this occurrence and create the next daily or weekly instance."""
        target_day = day if day is not None else date.today()
        if not self.is_due_on(target_day):
            raise ValueError("Cannot complete a task that is not due on that date.")
        if self.is_completed_on(target_day):
            raise ValueError("This task is already complete for that date.")
        self.completed_dates.add(target_day)
        if self.frequency == "once":
            return None

        interval_days = 1 if self.frequency == "daily" else 7
        next_date = target_day + timedelta(days=interval_days)
        return Task(
            description=self.description,
            scheduled_at=datetime.combine(next_date, self.scheduled_at.time()),
            duration_minutes=self.duration_minutes,
            frequency=self.frequency,
            priority=self.priority,
        )

    def mark_completed(self, day: date) -> Task | None:
        """Mark this task's occurrence complete on the specified date."""
        return self.mark_complete(day)


@dataclass
class Pet:
    name: str
    species: str
    age: int | None = None
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task to this pet."""
        self.tasks.append(task)


@dataclass
class Owner:
    name: str
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, name: str, species: str, age: int | None = None) -> Pet:
        """Create a pet, add it to this owner, and return it."""
        pet = Pet(name=name, species=species, age=age)
        self.pets.append(pet)
        return pet

    def get_all_tasks(self) -> list[Task]:
        """Return the tasks belonging to all of this owner's pets."""
        return [task for pet in self.pets for task in pet.tasks]


@dataclass
class Scheduler:
    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted chronologically by their scheduled time."""
        return sorted(tasks, key=lambda task: task.scheduled_at.strftime("%H:%M"))

    def detect_conflicts(
        self, owner: Owner, day: date | None = None
    ) -> list[str]:
        """Return warnings for pending tasks with identical times on the same day."""
        target_day = day if day is not None else date.today()
        tasks_by_time: dict[datetime, list[tuple[str, Task]]] = {}
        for pet in owner.pets:
            for task in pet.tasks:
                if task.is_due_on(target_day) and not task.is_completed_on(target_day):
                    tasks_by_time.setdefault(task.scheduled_at, []).append((pet.name, task))

        warnings = []
        for scheduled_at, scheduled_tasks in tasks_by_time.items():
            if len(scheduled_tasks) < 2:
                continue
            conflicting_tasks = "; ".join(
                f"{pet_name}: {task.description}"
                for pet_name, task in scheduled_tasks
            )
            warnings.append(
                f"Schedule conflict at {scheduled_at.strftime('%I:%M %p').lstrip('0')}: "
                f"{conflicting_tasks}"
            )
        return warnings

    def filter_tasks(
        self,
        owner: Owner,
        day: date | None = None,
        completed: bool | None = None,
        pet_name: str | None = None,
    ) -> list[Task]:
        """Filter owner-wide tasks by completion status and/or pet name."""
        target_day = day if day is not None else date.today()
        matching_pets = [
            pet
            for pet in owner.pets
            if pet_name is None or pet.name.casefold() == pet_name.casefold()
        ]
        tasks = [task for pet in matching_pets for task in pet.tasks]
        if completed is not None:
            tasks = [
                task
                for task in tasks
                if task.is_completed_on(target_day) is completed
            ]
        return tasks

    def get_tasks(
        self,
        owner: Owner,
        day: date | None = None,
        include_completed: bool = False,
    ) -> list[Task]:
        """Return due owner-wide tasks sorted by time and then priority."""
        target_day = day if day is not None else date.today()
        tasks = [
            task
            for task in owner.get_all_tasks()
            if task.is_due_on(target_day)
            and (include_completed or not task.is_completed_on(target_day))
        ]
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(
            tasks,
            key=lambda task: (
                task.scheduled_at.time(),
                priority_order[task.priority],
            ),
        )

    def mark_task_complete(
        self, owner: Owner, task: Task, day: date | None = None
    ) -> Task | None:
        """Complete an owner's task and attach its next occurrence when recurring."""
        pet = next(
            (
                pet
                for pet in owner.pets
                if any(owned_task is task for owned_task in pet.tasks)
            ),
            None,
        )
        if pet is None:
            raise ValueError("The task must belong to one of this owner's pets.")

        next_task = task.mark_complete(day)
        if next_task is not None:
            pet.add_task(next_task)
        return next_task

    def complete_task(
        self, owner: Owner, task: Task, day: date | None = None
    ) -> Task | None:
        """Complete an owner's task and return its next occurrence if recurring."""
        return self.mark_task_complete(owner, task, day)
