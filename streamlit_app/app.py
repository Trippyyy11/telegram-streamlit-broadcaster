import streamlit as st
import sqlite3
import os
import json
import uuid
from datetime import datetime
import pandas as pd

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="Telegram Broadcaster",
    page_icon="📢",
    layout="wide"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "local_agent", "storage.db")
ENTITIES_PATH = os.path.join(BASE_DIR, "local_agent", "telegram_entities.json")
TASKS_DIR = os.path.join(BASE_DIR, "local_agent", "tasks")

os.makedirs(TASKS_DIR, exist_ok=True)

# ---------------- DATABASE ----------------
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = conn.cursor()

# Existing tables (UNCHANGED)
cur.execute("""
CREATE TABLE IF NOT EXISTS folders (
    name TEXT PRIMARY KEY
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS folder_entities (
    folder TEXT,
    entity_id INTEGER,
    label TEXT
)
""")

# ✅ NEW TABLE (ADDITIVE ONLY)
cur.execute("""
CREATE TABLE IF NOT EXISTS message_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    task_type TEXT,
    folders TEXT,
    recipients INTEGER,
    has_media INTEGER,
    created_at TEXT
)
""")

conn.commit()

# ---------------- LOAD ENTITIES ----------------
with open(ENTITIES_PATH, "r", encoding="utf-8") as f:
    entities = json.load(f)

ENTITY_LABELS = {
    f"{e['name']} ({e['type']})": e["id"]
    for e in entities
}

# ---------------- SIDEBAR ----------------
st.sidebar.title("📂 Navigation")
page = st.sidebar.radio(
    "Choose section",
    [
        "Folder Manager",
        "Send Message",
        "Send / Schedule Quiz",
        "Message History",
        "Task Queue" # ✅ NEW
    ]
)

# =========================================================
# 📂 FOLDER MANAGER (UNCHANGED)
# =========================================================
if page == "Folder Manager":
    st.header("📂 Folder Manager")

    col1, col2 = st.columns([3, 1])
    with col1:
        new_folder = st.text_input("Create new folder")
    with col2:
        if st.button("➕ Create"):
            if new_folder.strip():
                cur.execute("INSERT OR IGNORE INTO folders VALUES (?)", (new_folder,))
                conn.commit()
                st.success("Folder created")

    st.divider()

    cur.execute("SELECT name FROM folders ORDER BY name")
    folders = [f[0] for f in cur.fetchall()]

    for fname in folders:
        with st.expander(f"📁 {fname}"):
            cur.execute(
                "SELECT label FROM folder_entities WHERE folder=?",
                (fname,)
            )
            current = [r[0] for r in cur.fetchall()]

            selected = st.multiselect(
                "Add / Remove groups & contacts",
                ENTITY_LABELS.keys(),
                default=current,
                key=f"sel_{fname}"
            )

            c1, c2 = st.columns(2)
            with c1:
                if st.button("💾 Save", key=f"save_{fname}"):
                    cur.execute("DELETE FROM folder_entities WHERE folder=?", (fname,))
                    for label in selected:
                        cur.execute(
                            "INSERT INTO folder_entities VALUES (?,?,?)",
                            (fname, ENTITY_LABELS[label], label)
                        )
                    conn.commit()
                    st.success("Folder updated")

            with c2:
                if st.button("🗑️ Delete Folder", key=f"del_{fname}"):
                    cur.execute("DELETE FROM folder_entities WHERE folder=?", (fname,))
                    cur.execute("DELETE FROM folders WHERE name=?", (fname,))
                    conn.commit()
                    st.warning("Folder deleted")
                    st.experimental_rerun()

# =========================================================
# ✉️ SEND MESSAGE (LOGGING ADDED)
# =========================================================
elif page == "Send Message":
    st.header("✉️ Send Message")

    cur.execute("SELECT name FROM folders ORDER BY name")
    folders = [f[0] for f in cur.fetchall()]

    selected_folders = st.multiselect("Select folders", folders)
    message = st.text_area("Message content", height=150)
    media = st.file_uploader("Attach image/file (optional)", type=None)

    schedule = st.checkbox("📅 Schedule for later")
    send_time = None
    if schedule:
        send_time = st.datetime_input("Send at", min_value=datetime.now())

    if st.button("🚀 Send Message"):
        recipient_ids = []
        for f in selected_folders:
            cur.execute("SELECT entity_id FROM folder_entities WHERE folder=?", (f,))
            recipient_ids.extend([r[0] for r in cur.fetchall()])

        task_id = str(uuid.uuid4())
        task = {
            "type": "message",
            "recipients": list(set(recipient_ids)),
            "content": message,
            "send_at": send_time.isoformat() if send_time else None,
            "media": media.name if media else None
        }

        with open(os.path.join(TASKS_DIR, f"{task_id}.json"), "w") as f:
            json.dump(task, f, indent=2)

        # ✅ LOG ENTRY
        cur.execute("""
            INSERT INTO message_logs
            (task_id, task_type, folders, recipients, has_media, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            "message",
            ",".join(selected_folders),
            len(set(recipient_ids)),
            1 if media else 0,
            datetime.now().isoformat()
        ))
        conn.commit()

        st.success("Message queued successfully")

# =========================================================
# 📊 QUIZ (LOGGING ADDED)
# =========================================================
elif page == "Send / Schedule Quiz":
    st.header("📊 Quiz / Poll")

    cur.execute("SELECT name FROM folders ORDER BY name")
    folders = [f[0] for f in cur.fetchall()]
    selected_folders = st.multiselect("Select folders", folders)

    question = st.text_input("Question")
    options = [st.text_input(f"Option {i+1}") for i in range(4)]
    correct = st.selectbox("Correct option", [0, 1, 2, 3])

    schedule = st.checkbox("📅 Schedule quiz")
    send_time = datetime.now()
    if schedule:
        send_time = st.datetime_input("Send at", min_value=datetime.now())

    if st.button("📤 Send Quiz"):
        recipient_ids = []
        for f in selected_folders:
            cur.execute("SELECT entity_id FROM folder_entities WHERE folder=?", (f,))
            recipient_ids.extend([r[0] for r in cur.fetchall()])

        task_id = str(uuid.uuid4())
        task = {
            "type": "poll",
            "recipients": list(set(recipient_ids)),
            "content": {
                "question": question,
                "options": options,
                "correct": correct
            },
            "send_at": send_time.isoformat()
        }

        with open(os.path.join(TASKS_DIR, f"{task_id}.json"), "w") as f:
            json.dump(task, f, indent=2)

        # ✅ LOG ENTRY
        cur.execute("""
            INSERT INTO message_logs
            (task_id, task_type, folders, recipients, has_media, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            task_id,
            "quiz",
            ",".join(selected_folders),
            len(set(recipient_ids)),
            0,
            datetime.now().isoformat()
        ))
        conn.commit()

        st.success("Quiz queued successfully")

# =========================================================
# 📜 MESSAGE HISTORY (NEW)
# =========================================================
elif page == "Message History":
    st.header("📜 Message History")

    col1, col2 = st.columns(2)
    with col1:
        filter_type = st.selectbox(
            "Filter by type",
            ["All", "message", "quiz"]
        )
    with col2:
        folder_filter = st.text_input("Filter by folder (optional)")

    query = "SELECT * FROM message_logs ORDER BY created_at DESC"
    df = pd.read_sql_query(query, conn)

    if filter_type != "All":
        df = df[df["task_type"] == filter_type]

    if folder_filter:
        df = df[df["folders"].str.contains(folder_filter, case=False)]

    st.dataframe(df, use_container_width=True)

    st.download_button(
        "⬇️ Download CSV",
        data=df.to_csv(index=False),
        file_name="message_history.csv",
        mime="text/csv"
    )
# =========================================================
# 📦 TASK QUEUE VIEWER + CANCEL
# =========================================================
elif page == "Task Queue":
    st.header("📦 Pending Task Queue")

    task_files = sorted(
        [f for f in os.listdir(TASKS_DIR) if f.endswith(".json")],
        reverse=True
    )

    if not task_files:
        st.info("No pending tasks in queue.")
    else:
        rows = []

        for file in task_files:
            path = os.path.join(TASKS_DIR, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    task = json.load(f)

                rows.append({
                    "Task ID": file.replace(".json", ""),
                    "Type": task.get("type"),
                    "Scheduled At": task.get("send_at") or "Immediate",
                    "Recipients": len(task.get("recipients", [])),
                    "File": file
                })
            except Exception as e:
                rows.append({
                    "Task ID": file.replace(".json", ""),
                    "Type": "❌ Corrupt",
                    "Scheduled At": "N/A",
                    "Recipients": "N/A",
                    "File": file
                })

        df = pd.DataFrame(rows)

        st.dataframe(
            df.drop(columns=["File"]),
            use_container_width=True
        )

        st.divider()
        st.subheader("❌ Cancel a Task")

        task_to_cancel = st.selectbox(
            "Select task to cancel",
            df["Task ID"].tolist()
        )

        if st.button("🗑️ Cancel Selected Task"):
            file_name = task_to_cancel + ".json"
            file_path = os.path.join(TASKS_DIR, file_name)

            if os.path.exists(file_path):
                os.remove(file_path)
                st.success(f"Task {task_to_cancel} cancelled successfully.")
                st.rerun()
            else:
                st.error("Task file not found (already processed?).")

        st.caption(
            "ℹ️ Canceling removes the task from queue before the daemon processes it."
        )
