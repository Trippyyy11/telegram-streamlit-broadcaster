import streamlit as st
import sqlite3
import os
import json
import uuid
from datetime import datetime
import pandas as pd
import subprocess
import altair as alt

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

# Existing tables
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

# Message Logs with task_name
cur.execute("""
CREATE TABLE IF NOT EXISTS message_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    task_name TEXT,
    task_type TEXT,
    folders TEXT,
    recipients INTEGER,
    has_media INTEGER,
    created_at TEXT
)
""")

# Sent Messages for tracking IDs
cur.execute("""
CREATE TABLE IF NOT EXISTS sent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    chat_id INTEGER,
    message_id INTEGER,
    sent_at TEXT,
    status TEXT,
    views INTEGER DEFAULT 0,
    forwards INTEGER DEFAULT 0,
    reactions INTEGER DEFAULT 0,
    last_updated TEXT
)
""")

# Migration for existing databases
try:
    cur.execute("ALTER TABLE message_logs ADD COLUMN task_name TEXT")
except sqlite3.OperationalError:
    pass 

# Migration for sent_messages analytics
# We must do them one by one because if one fails (column exists), the rest in the block are skipped
migrations = [
    "ALTER TABLE sent_messages ADD COLUMN views INTEGER DEFAULT 0",
    "ALTER TABLE sent_messages ADD COLUMN forwards INTEGER DEFAULT 0",
    "ALTER TABLE sent_messages ADD COLUMN reactions INTEGER DEFAULT 0",
    "ALTER TABLE sent_messages ADD COLUMN replies INTEGER DEFAULT 0",
    "ALTER TABLE sent_messages ADD COLUMN last_updated TEXT"
]

for cmd in migrations:
    try:
        cur.execute(cmd)
    except sqlite3.OperationalError:
        pass 

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
        "Data Tracking",
        "Dashboard",
        "Task Queue"
    ]
)

# =========================================================
# 📂 FOLDER MANAGER
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
                    st.rerun()

# =========================================================
# ✉️ SEND MESSAGE
# =========================================================
elif page == "Send Message":
    st.header("✉️ Send Message")

    cur.execute("SELECT name FROM folders ORDER BY name")
    folders = [f[0] for f in cur.fetchall()]

    selected_folders = st.multiselect("Select folders", folders)
    
    # NEW: Task Name
    task_name = st.text_input("Task Name (Optional)", help="Identify this broadcast in history")
    
    message = st.text_area("Message content", height=150)
    media = st.file_uploader("Attach image/file (optional)", type=None)

    # NEW: Expiration
    col_sched, col_expire = st.columns(2)
    with col_sched:
        schedule = st.checkbox("📅 Schedule for later")
        send_time = None
        if schedule:
            send_time = st.datetime_input("Send at", min_value=datetime.now())
    
    with col_expire:
        expires_in = st.number_input("⏳ Temporary Message (Expires in hours)", min_value=0.0, step=0.1, help="0 to disable. Message will auto-delete after this time.")

    if st.button("🚀 Send Message"):
        recipient_ids = []
        for f in selected_folders:
            cur.execute("SELECT entity_id FROM folder_entities WHERE folder=?", (f,))
            recipient_ids.extend([r[0] for r in cur.fetchall()])
            
        if not recipient_ids:
             st.error("No recipients found in selected folders.")
        else:
            task_id = str(uuid.uuid4())
            task = {
                "type": "message",
                "recipients": list(set(recipient_ids)),
                "content": message,
                "send_at": send_time.isoformat() if send_time else None,
                "media": media.name if media else None,
                "expires_in_hours": expires_in,
                "task_name": task_name
            }

            with open(os.path.join(TASKS_DIR, f"{task_id}.json"), "w") as f:
                json.dump(task, f, indent=2)

            # LOG ENTRY
            cur.execute("""
                INSERT INTO message_logs
                (task_id, task_name, task_type, folders, recipients, has_media, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                task_name if task_name else "Untitled",
                "message",
                ",".join(selected_folders),
                len(set(recipient_ids)),
                1 if media else 0,
                datetime.now().isoformat()
            ))
            conn.commit()

            st.success("Message queued successfully")

# =========================================================
# 📊 QUIZ
# =========================================================
elif page == "Send / Schedule Quiz":
    st.header("📊 Quiz / Poll")

    cur.execute("SELECT name FROM folders ORDER BY name")
    folders = [f[0] for f in cur.fetchall()]
    selected_folders = st.multiselect("Select folders", folders)
    
    task_name = st.text_input("Task Name (Optional)", help="Identify this quiz in history")

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

        if not recipient_ids:
            st.error("No recipients found.")
        else:
            task_id = str(uuid.uuid4())
            task = {
                "type": "poll",
                "recipients": list(set(recipient_ids)),
                "content": {
                    "question": question,
                    "options": options,
                    "correct": correct
                },
                "send_at": send_time.isoformat(),
                "task_name": task_name
            }

            with open(os.path.join(TASKS_DIR, f"{task_id}.json"), "w") as f:
                json.dump(task, f, indent=2)

            cur.execute("""
                INSERT INTO message_logs
                (task_id, task_name, task_type, folders, recipients, has_media, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                task_name if task_name else "Untitled",
                "quiz",
                ",".join(selected_folders),
                len(set(recipient_ids)),
                0,
                datetime.now().isoformat()
            ))
            conn.commit()

            st.success("Quiz queued successfully")

# =========================================================
# 📜 MESSAGE HISTORY
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

    # Custom Table Layout with Undo Button
    # Headers
    h1, h2, h3, h4, h5, h6 = st.columns([2, 1, 2, 1, 1, 1])
    h1.write("**Task Name (ID)**")
    h2.write("**Type**")
    h3.write("**Folders**")
    h4.write("**Recipients**")
    h5.write("**Created At**")
    h6.write("**Action**")
    
    st.divider()

    if df.empty:
        st.info("No message history found.")
    else:
        for idx, row in df.iterrows():
            c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 2, 1, 1, 1])
            
            with c1:
                st.write(f"{row['task_name']} \n\n`{row['task_id']}`")
            with c2:
                st.write(row['task_type'])
            with c3:
                st.write(row['folders'])
            with c4:
                st.write(f"{row['recipients']}")
            with c5:
                st.write(row['created_at'])
            with c6:
                if st.button("🗑️ Undo", key=f"undo_btn_{row['task_id']}"):
                    # Undo Logic
                    cur.execute("SELECT chat_id, message_id FROM sent_messages WHERE task_id = ? AND status != 'deleted'", (row['task_id'],))
                    sent_msgs = cur.fetchall()
                    
                    if not sent_msgs:
                        st.warning("No active messages.")
                    else:
                        count = 0
                        for cid, mid in sent_msgs:
                            del_task = {
                                "type": "delete_message",
                                "chat_id": cid,
                                "message_id": mid,
                                "send_at": datetime.now().isoformat()
                            }
                            # Queue deletion
                            del_fname = f"undo_{uuid.uuid4()}.json"
                            with open(os.path.join(TASKS_DIR, del_fname), "w") as f:
                                json.dump(del_task, f)
                            count += 1
                        st.toast(f"Queued undo for {count} msgs!", icon="✅")

    st.divider()
    
    st.download_button(
        "⬇️ Download CSV",
        data=df.to_csv(index=False),
        file_name="message_history.csv",
        mime="text/csv"
    )

# =========================================================
# 📈 DATA TRACKING
# =========================================================
elif page == "Data Tracking":
    st.header("📈 Data Tracking")
    st.caption("Fetch real-time views and forward counts from Telegram (via Userbot).")
    
    if st.button("🔄 Refresh Analytics"):
        with st.spinner("Fetching latest stats from Telegram... (This may take a few seconds)"):
            try:
                # Call analytics_engine.py
                analytics_script = os.path.join(BASE_DIR, "local_agent", "analytics_engine.py")
                result = subprocess.run(["python", analytics_script], capture_output=True, text=True)
                if result.returncode == 0:
                    st.success("Analytics updated via Telethon!")
                else:
                    st.error(f"Failed to update: {result.stderr}")
            except Exception as e:
                st.error(f"Error running analytics engine: {e}")
    
    st.divider()
    
    # Show Table
    # Join with message_logs to get Task Name if possible
    query = """
    SELECT sm.task_id, ml.task_name, sm.chat_id, sm.message_id, sm.status, sm.views, sm.forwards, sm.reactions, sm.replies AS comments, sm.last_updated
    FROM sent_messages sm
    LEFT JOIN message_logs ml ON sm.task_id = ml.task_id
    WHERE sm.status = 'sent'
    ORDER BY sm.sent_at DESC
    """
    df = pd.read_sql_query(query, conn)
    
    st.dataframe(df, use_container_width=True)

# =========================================================
# 📊 DASHBOARD
# =========================================================
elif page == "Dashboard":
    st.header("📊 Dashboard")
    
    # Metrics
    cur.execute("SELECT COUNT(*), SUM(views), SUM(forwards), SUM(replies) FROM sent_messages WHERE status='sent'")
    total_sent, total_views, total_forwards, total_comments = cur.fetchone()
    
    cur.execute("SELECT COUNT(*) FROM sent_messages WHERE status='deleted'")
    total_deleted = cur.fetchone()[0]
    
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Messages Sent", total_sent or 0)
    m2.metric("Total Views", total_views or 0)
    m3.metric("Total Forwards", total_forwards or 0)
    m4.metric("Total Comments", total_comments or 0)
    m5.metric("Msgs Recalled", total_deleted or 0)
    
    st.divider()
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("Performance by Task")
        # Top 5 Tasks by Views
        query = """
        SELECT ml.task_name, SUM(sm.views) as total_views
        FROM sent_messages sm
        JOIN message_logs ml ON sm.task_id = ml.task_id
        GROUP BY ml.task_name
        ORDER BY total_views DESC
        LIMIT 10
        """
        df_views = pd.read_sql_query(query, conn)
        
        if not df_views.empty:
            chart = alt.Chart(df_views).mark_bar().encode(
                x='total_views',
                y=alt.Y('task_name', sort='-x'),
                tooltip=['task_name', 'total_views']
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No data yet.")
            
    with c2:
        st.subheader("Message Status")
        # Pie Chart of Status
        df_status = pd.read_sql_query("SELECT status, COUNT(*) as count FROM sent_messages GROUP BY status", conn)
        
        if not df_status.empty:
            chart = alt.Chart(df_status).mark_arc().encode(
                theta='count',
                color='status',
                tooltip=['status', 'count']
            ).properties(height=300)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No data yet.")

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
                    # Handle empty files potentially
                    try:
                        task = json.load(f)
                    except json.JSONDecodeError:
                        task = {}

                rows.append({
                    "Task ID": file.replace(".json", ""),
                    "Type": task.get("type", "Unknown"),
                    "Scheduled At": task.get("send_at") or "Immediate",
                    "Recipients": len(task.get("recipients", [])),
                    "File": file
                })
            except Exception as e:
                rows.append({
                    "Task ID": file,
                    "Type": "❌ Error",
                    "Scheduled At": str(e),
                    "File": file
                })

        df = pd.DataFrame(rows)

        st.dataframe(
            df.drop(columns=["File"]),
            use_container_width=True
        )

        st.divider()
        st.subheader("❌ Cancel a Task")

        if not df.empty:
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
