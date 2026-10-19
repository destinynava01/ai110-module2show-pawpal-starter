from datetime import date, datetime, time

from pawpal_system import Owner, Scheduler, Task


def main() -> None:
    owner = Owner("Jordan")
    mochi = owner.add_pet("Mochi", "dog", age=3)
    luna = owner.add_pet("Luna", "cat", age=5)

    today = date.today()
    mochi.add_task(
        Task(
            description="Evening feeding",
            scheduled_at=datetime.combine(today, time(18, 0)),
            duration_minutes=15,
            frequency="daily",
            priority="medium",
        )
    )
    luna.add_task(
        Task(
            description="Breakfast",
            scheduled_at=datetime.combine(today, time(8, 0)),
            duration_minutes=10,
            frequency="daily",
            priority="high",
        )
    )
    mochi.add_task(
        Task(
            description="Morning walk",
            scheduled_at=datetime.combine(today, time(8, 0)),
            duration_minutes=30,
            frequency="daily",
            priority="high",
        )
    )

    scheduler = Scheduler()

    def print_tasks(tasks: list[Task]) -> None:
        pet_by_task = {
            id(task): pet.name
            for pet in owner.pets
            for task in pet.tasks
        }
        for task in tasks:
            scheduled_time = task.scheduled_at.strftime("%I:%M %p").lstrip("0")
            print(
                f"{scheduled_time} - {pet_by_task[id(task)]}: {task.description} "
                f"({task.duration_minutes} min, {task.priority} priority)"
            )

    print(f"Today's Schedule for {owner.name} (sorted by time)")
    print_tasks(scheduler.sort_by_time(owner.get_all_tasks()))
    for warning in scheduler.detect_conflicts(owner, today):
        print(f"WARNING: {warning}")

    breakfast = luna.tasks[0]
    next_breakfast = scheduler.mark_task_complete(owner, breakfast, today)
    print("\nCompleted tasks:")
    print_tasks(
        scheduler.sort_by_time(
            scheduler.filter_tasks(owner, day=today, completed=True)
        )
    )
    if next_breakfast is not None:
        print(
            "\nNext breakfast occurrence: "
            f"{next_breakfast.scheduled_at.strftime('%Y-%m-%d %I:%M %p').lstrip('0')}"
        )

    print("\nMochi's tasks:")
    print_tasks(
        scheduler.sort_by_time(
            scheduler.filter_tasks(owner, day=today, pet_name="Mochi")
        )
    )


if __name__ == "__main__":
    main()