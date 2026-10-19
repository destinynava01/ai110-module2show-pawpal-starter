from datetime import date, datetime, time

import streamlit as st

from pawpal_system import Owner, Scheduler, Task


st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")
st.markdown("Add pets and care tasks, then review the schedule across your pets.")

owner_name = st.text_input("Owner name", value="Jordan")
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name=owner_name)
else:
    st.session_state.owner.name = owner_name
owner = st.session_state.owner

st.divider()
st.subheader("Pets")
with st.form("add_pet_form", clear_on_submit=True):
    new_pet_name = st.text_input("Pet name")
    new_pet_species = st.selectbox("Species", ["dog", "cat", "other"])
    new_pet_age = st.number_input("Age (years)", min_value=0, max_value=100, value=0)
    add_pet_submitted = st.form_submit_button("Add pet")

if add_pet_submitted:
    if not new_pet_name.strip():
        st.error("Enter a name for the pet.")
    else:
        owner.add_pet(new_pet_name.strip(), new_pet_species, int(new_pet_age))
        st.success(f"Added {new_pet_name.strip()}.")

if owner.pets:
    st.write("Your pets:")
    st.write(", ".join(f"{pet.name} ({pet.species})" for pet in owner.pets))
else:
    st.info("Add a pet before scheduling care tasks.")

if owner.pets:
    st.divider()
    st.subheader("Schedule a Task")
    pet_indices = list(range(len(owner.pets)))
    with st.form("add_task_form", clear_on_submit=True):
        selected_pet_index = st.selectbox(
            "For pet",
            pet_indices,
            format_func=lambda index: (
                f"{owner.pets[index].name} ({owner.pets[index].species})"
            ),
        )
        task_description = st.text_input("Task description")
        task_date = st.date_input("Date", value=date.today())
        task_time = st.time_input("Time", value=time(8, 0))
        duration = st.number_input(
            "Duration (minutes)", min_value=1, max_value=240, value=20
        )
        frequency = st.selectbox("Frequency", ["once", "daily", "weekly"])
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
        add_task_submitted = st.form_submit_button("Schedule task")

    if add_task_submitted:
        if not task_description.strip():
            st.error("Enter a description for the task.")
        else:
            task = Task(
                description=task_description.strip(),
                scheduled_at=datetime.combine(task_date, task_time),
                duration_minutes=int(duration),
                frequency=frequency,
                priority=priority,
            )
            pet = owner.pets[selected_pet_index]
            pet.add_task(task)
            st.success(f"Scheduled '{task.description}' for {pet.name}.")

st.divider()
st.subheader("Today's Schedule")
schedule_date = st.date_input(
    "Show tasks for", value=date.today(), key="schedule_date"
)
scheduler = Scheduler()
scheduled_tasks = scheduler.get_tasks(owner, schedule_date, include_completed=True)

for warning in scheduler.detect_conflicts(owner, schedule_date):
    st.warning(warning)

if scheduled_tasks:
    task_rows = []
    for task in scheduled_tasks:
        pet_name = next(
            pet.name
            for pet in owner.pets
            if any(pet_task is task for pet_task in pet.tasks)
        )
        task_rows.append(
            {
                "Time": task.scheduled_at.strftime("%I:%M %p").lstrip("0"),
                "Pet": pet_name,
                "Task": task.description,
                "Duration (minutes)": task.duration_minutes,
                "Priority": task.priority,
                "Status": (
                    "completed"
                    if task.is_completed_on(schedule_date)
                    else "pending"
                ),
            }
        )
    st.table(task_rows)
else:
    st.info("No tasks scheduled for this day.")
