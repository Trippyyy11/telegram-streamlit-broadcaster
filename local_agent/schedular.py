import json
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

scheduler = BackgroundScheduler()
scheduler.start()


def schedule_task(task_file):
    with open(task_file, "r") as f:
        task = json.load(f)

    send_at = task.get("send_at")
    if not send_at:
        print("No schedule found in task.")
        return

    run_time = datetime.fromisoformat(send_at)

    scheduler.add_job(
        subprocess.call,
        trigger="date",
        run_date=run_time,
        args=(["python", "agent.py", task_file],)
    )

    print(f"Task scheduled at {run_time}")


if __name__ == "__main__":
    schedule_task("task.json")
    input("Scheduler running. Press Enter to exit...")
