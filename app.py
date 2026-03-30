import os
import time
from statistics import mean, pstdev

import pandas as pd
import psutil
import streamlit as st
from streamlit_autorefresh import st_autorefresh


st.set_page_config(page_title="Process Monitoring Dashboard", page_icon="🖥️", layout="wide")

st.markdown(
    """
<style>
[data-testid="stAppViewContainer"] {
  opacity: 1 !important;
}
  .stApp { background: radial-gradient(1200px 700px at 20% 0%, rgba(98, 124, 255, 0.18), transparent 60%),
                     radial-gradient(900px 600px at 95% 20%, rgba(0, 201, 167, 0.14), transparent 60%),
                     radial-gradient(700px 500px at 10% 90%, rgba(255, 171, 64, 0.10), transparent 55%),
                     #0b1020; color: #e7eaf3; }
  [data-testid="stHeader"] { background: transparent; }
  [data-testid="stSidebar"] { background: rgba(10, 14, 28, 0.65); }
  div[data-testid="stMetricValue"] { color: #e7eaf3; }
  div[data-testid="stMetricLabel"] { color: rgba(231, 234, 243, 0.78); }
  .block-container { padding-top: 1.1rem; }
  div[data-testid="stNotificationContentWarning"] { background: rgba(255, 193, 7, 0.18); border: 1px solid rgba(255, 193, 7, 0.35); }
  div[data-testid="stNotificationContentError"] { background: rgba(244, 67, 54, 0.16); border: 1px solid rgba(244, 67, 54, 0.35); }
  .stDataFrame { background: rgba(10, 14, 28, 0.35); border-radius: 14px; }
  .state-badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .running { background: rgba(34, 197, 94, 0.2); color: #86efac; }
  .sleeping { background: rgba(59, 130, 246, 0.2); color: #93c5fd; }
  .stopped { background: rgba(245, 158, 11, 0.2); color: #fcd34d; }
  .zombie { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
  .other { background: rgba(148, 163, 184, 0.2); color: #cbd5e1; }
</style>
""",
    unsafe_allow_html=True,
)

st_autorefresh(interval=3000, key="auto_refresh")


def format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(max(value, 0))
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return f"{value} B"


def normalize_status(status: str) -> str:
    raw = (status or "").lower().strip()
    if raw in {"running"}:
        return "running"
    if raw in {"sleeping", "idle", "disk-sleep", "waking"}:
        return "sleeping"
    if raw in {"stopped", "tracing-stop"}:
        return "stopped"
    if raw in {"zombie", "dead"}:
        return "zombie"
    return "other"


def status_badge_html(status: str) -> str:
    label = status.capitalize()
    cls = status if status in {"running", "sleeping", "stopped", "zombie"} else "other"
    return f"<span class='state-badge {cls}'>{label}</span>"


def status_indicator(status: str) -> str:
    icons = {"running": "🟢", "sleeping": "🔵", "stopped": "🟠", "zombie": "🔴", "other": "⚪"}
    return f"{icons.get(status, '⚪')} {status.capitalize()}"


def append_series_point(key: str, value: float, max_points: int = 120) -> None:
    data = st.session_state.get(key, [])
    if not isinstance(data, list):
        data = []
    data.append(float(value))
    if len(data) > max_points:
        data = data[-max_points:]
    st.session_state[key] = data


def series_frame(values: list[float], column: str) -> pd.DataFrame:
    if not values:
        return pd.DataFrame({column: []})
    index = list(range(len(values)))
    frame = pd.DataFrame({column: values}, index=index)
    return frame


def detect_spike_and_trend(values: list[float], high_threshold: float) -> tuple[bool, bool, str]:
    if len(values) < 8:
        latest = values[-1] if values else 0.0
        return latest > high_threshold, False, "insufficient history"
    latest = values[-1]
    baseline = values[:-1]
    base_mean = mean(baseline)
    base_std = pstdev(baseline) if len(baseline) > 1 else 0.0
    spike = latest > base_mean + max(10.0, 2 * base_std)
    recent = values[-5:]
    previous = values[-10:-5]
    recent_mean = mean(recent)
    previous_mean = mean(previous) if previous else recent_mean
    trend_up = recent_mean > previous_mean + 7
    sustained_high = all(v > high_threshold for v in recent[-3:])
    if sustained_high:
        return True, trend_up, "sustained high"
    if spike and trend_up:
        return True, True, "spike with rising trend"
    if spike:
        return True, False, "spike detected"
    return latest > high_threshold, trend_up, "trend check"


def get_system_snapshot() -> dict:
    cpu_total = float(psutil.cpu_percent(interval=None))
    cpu_cores = [float(v) for v in psutil.cpu_percent(interval=None, percpu=True)]
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))
    disk_io = psutil.disk_io_counters()
    return {
        "cpu_total": cpu_total,
        "cpu_cores": cpu_cores,
        "memory_percent": float(memory.percent),
        "memory_total": int(memory.total),
        "memory_used": int(memory.used),
        "memory_available": int(memory.available),
        "memory_cached": int(getattr(memory, "cached", 0)),
        "swap_percent": float(swap.percent),
        "swap_used": int(swap.used),
        "swap_total": int(swap.total),
        "disk_percent": float(disk.percent),
        "disk_used": int(disk.used),
        "disk_total": int(disk.total),
        "disk_read": int(disk_io.read_bytes) if disk_io else 0,
        "disk_write": int(disk_io.write_bytes) if disk_io else 0,
        "process_count": len(psutil.pids()),
    }


def get_process_rows() -> list[dict]:
    rows: list[dict] = []
    process_trends = st.session_state.setdefault("process_trends", {})
    timestamp = int(time.time())
    for proc in psutil.process_iter(attrs=["pid", "name", "status"]):
        try:
            with proc.oneshot():
                pid = int(proc.pid)
                process_name = (proc.info.get("name") or "").strip() or "Unknown"
                cpu_value = float(proc.cpu_percent(interval=None))
                mem_value = float(proc.memory_percent())
                state = normalize_status(proc.info.get("status") or "")
            entry = process_trends.get(pid, {"name": process_name, "cpu": [], "mem": [], "seen": timestamp})
            entry["name"] = process_name
            entry["seen"] = timestamp
            entry["cpu"].append(cpu_value)
            entry["mem"].append(mem_value)
            entry["cpu"] = entry["cpu"][-30:]
            entry["mem"] = entry["mem"][-30:]
            process_trends[pid] = entry
            cpu_trend = mean(entry["cpu"][-5:]) - mean(entry["cpu"][-10:-5]) if len(entry["cpu"]) >= 10 else 0.0
            mem_trend = mean(entry["mem"][-5:]) - mean(entry["mem"][-10:-5]) if len(entry["mem"]) >= 10 else 0.0
            consistency = mean(entry["cpu"][-10:]) if len(entry["cpu"]) >= 5 else cpu_value
            rows.append(
                {
                    "PID": pid,
                    "Process Name": process_name,
                    "CPU Usage %": cpu_value,
                    "Memory Usage %": mem_value,
                    "Status": state,
                    "CPU Trend Δ": cpu_trend,
                    "Memory Trend Δ": mem_trend,
                    "Consistency Score": consistency,
                    "State Badge": status_badge_html(state),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
        except Exception:
            continue
    stale = [pid for pid, data in process_trends.items() if timestamp - int(data.get("seen", timestamp)) > 120]
    for pid in stale:
        process_trends.pop(pid, None)
    st.session_state["process_trends"] = process_trends
    rows.sort(key=lambda r: r["CPU Usage %"], reverse=True)
    return rows


def terminate_process(pid_text: str, confirm_kill: bool) -> None:
    pid_value = None
    try:
        pid_value = int((pid_text or "").strip())
    except Exception:
        st.error("Invalid PID.")
    if pid_value is None:
        return
    if pid_value <= 0:
        st.error("Invalid PID.")
        return
    if pid_value == os.getpid():
        st.error("Refusing to terminate this dashboard process.")
        return
    if not confirm_kill:
        st.error("Enable the confirmation checkbox to terminate a process.")
        return
    try:
        target = psutil.Process(pid_value)
        target_name = target.name()
        target.terminate()
        try:
            target.wait(timeout=2)
            st.success(f"Terminated PID {pid_value} ({target_name}).")
        except psutil.TimeoutExpired:
            st.warning(f"Sent terminate to PID {pid_value} ({target_name}). It may still be shutting down.")
    except psutil.NoSuchProcess:
        st.error("Process not found.")
    except psutil.AccessDenied:
        st.error("Permission denied. Try running as Administrator.")
    except Exception:
        st.error("Failed to terminate the process.")


system = get_system_snapshot()
append_series_point("cpu_history", system["cpu_total"])
append_series_point("mem_history", system["memory_percent"])

cpu_history = st.session_state.get("cpu_history", [])
mem_history = st.session_state.get("mem_history", [])
cpu_issue, cpu_rising, cpu_reason = detect_spike_and_trend(cpu_history, 80)
mem_issue, mem_rising, mem_reason = detect_spike_and_trend(mem_history, 80)

st.title("Real-Time Process Monitoring Dashboard")

row1 = st.columns(4)
row1[0].metric("CPU Usage", f"{system['cpu_total']:.1f}%")
row1[1].metric("Memory Usage", f"{system['memory_percent']:.1f}%", f"{format_bytes(system['memory_used'])} / {format_bytes(system['memory_total'])}")
row1[2].metric("Swap Usage", f"{system['swap_percent']:.1f}%", f"{format_bytes(system['swap_used'])} / {format_bytes(system['swap_total'])}")
row1[3].metric("Running Processes", f"{system['process_count']}")

row2 = st.columns(4)
row2[0].metric("Available Memory", format_bytes(system["memory_available"]))
row2[1].metric("Cached Memory", format_bytes(system["memory_cached"]))
row2[2].metric("Disk Usage", f"{system['disk_percent']:.1f}%", f"{format_bytes(system['disk_used'])} / {format_bytes(system['disk_total'])}")
row2[3].metric("Disk I/O", f"R {format_bytes(system['disk_read'])}", f"W {format_bytes(system['disk_write'])}")

if cpu_issue:
    st.warning(f"CPU issue detected: {cpu_reason}. Current {system['cpu_total']:.1f}%")
if mem_issue:
    st.warning(f"Memory issue detected: {mem_reason}. Current {system['memory_percent']:.1f}%")
if cpu_rising and not cpu_issue:
    st.info("CPU trend is rising even without threshold breach.")
if mem_rising and not mem_issue:
    st.info("Memory trend is rising even without threshold breach.")

chart_cols = st.columns(3)
with chart_cols[0]:
    st.subheader("CPU Usage Over Time")
    st.line_chart(series_frame(cpu_history, "CPU %"), height=220)
with chart_cols[1]:
    st.subheader("Memory Usage Over Time")
    st.line_chart(series_frame(mem_history, "Memory %"), height=220)
with chart_cols[2]:
    st.subheader("Per-Core CPU Usage")
    core_frame = pd.DataFrame({"Core": [f"Core {i}" for i in range(len(system["cpu_cores"]))], "CPU %": system["cpu_cores"]})
    st.bar_chart(core_frame.set_index("Core"), height=220)

st.divider()

process_rows = get_process_rows()
process_frame = pd.DataFrame(process_rows)
if process_frame.empty:
    process_frame = pd.DataFrame(
        columns=["PID", "Process Name", "CPU Usage %", "Memory Usage %", "Status", "CPU Trend Δ", "Memory Trend Δ", "Consistency Score", "State Badge"]
    )

status_counts = process_frame["Status"].value_counts().to_dict() if not process_frame.empty else {}
state_cols = st.columns(5)
for idx, state_name in enumerate(["running", "sleeping", "stopped", "zombie", "other"]):
    state_cols[idx].metric(state_name.capitalize(), int(status_counts.get(state_name, 0)))

controls = st.columns([1.6, 1.3, 1.2, 1.0, 1.2, 1.1, 1.2])
with controls[0]:
    search_query = st.text_input("Search process name", value=st.session_state.get("search_query", ""))
    st.session_state["search_query"] = search_query
with controls[1]:
    selected_states = st.multiselect(
        "Filter by state",
        options=["running", "sleeping", "stopped", "zombie", "other"],
        default=st.session_state.get("selected_states", ["running", "sleeping", "stopped", "zombie", "other"]),
    )
    st.session_state["selected_states"] = selected_states
with controls[2]:
    sort_by = st.selectbox(
        "Sort by",
        options=["CPU Usage %", "Memory Usage %", "CPU Trend Δ", "Memory Trend Δ", "Consistency Score", "PID", "Process Name"],
        index=["CPU Usage %", "Memory Usage %", "CPU Trend Δ", "Memory Trend Δ", "Consistency Score", "PID", "Process Name"].index(
            st.session_state.get("sort_by", "CPU Usage %")
        ),
    )
    st.session_state["sort_by"] = sort_by
with controls[3]:
    sort_desc = st.checkbox("Descending", value=st.session_state.get("sort_desc", True))
    st.session_state["sort_desc"] = sort_desc
with controls[4]:
    pid_text = st.text_input("PID to terminate", value=st.session_state.get("pid_text", ""))
    st.session_state["pid_text"] = pid_text
with controls[5]:
    confirm_kill = st.checkbox("Confirm kill", value=False)
with controls[6]:
    terminate_clicked = st.button("Terminate", use_container_width=True, type="primary")

if terminate_clicked:
    terminate_process(pid_text, confirm_kill)

filtered = process_frame.copy()
query = (search_query or "").strip().lower()
if query:
    filtered = filtered[filtered["Process Name"].str.lower().str.contains(query, na=False)]
if selected_states:
    filtered = filtered[filtered["Status"].isin(selected_states)]
filtered = filtered.sort_values(by=sort_by, ascending=not sort_desc).head(20).reset_index(drop=True)

high_consistent = filtered[(filtered["Consistency Score"] >= 25) | (filtered["Memory Usage %"] >= 12)]

insight_col1, insight_col2 = st.columns(2)
with insight_col1:
    st.subheader("Consistently High Resource Consumers")
    if high_consistent.empty:
        st.write("No consistently high consumers in the current top set.")
    else:
        st.dataframe(
            high_consistent[["PID", "Process Name", "CPU Usage %", "Memory Usage %", "Consistency Score", "Status"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "CPU Usage %": st.column_config.NumberColumn(format="%.2f"),
                "Memory Usage %": st.column_config.NumberColumn(format="%.2f"),
                "Consistency Score": st.column_config.NumberColumn(format="%.2f"),
            },
        )
with insight_col2:
    st.subheader("Process State Grouping")
    state_frame = pd.DataFrame({"State": list(status_counts.keys()), "Count": list(status_counts.values())})
    if state_frame.empty:
        st.write("No process state data available.")
    else:
        st.bar_chart(state_frame.set_index("State"), height=220)

st.subheader("Top Processes")
display_frame = filtered.copy()
display_frame["State Badge"] = display_frame["Status"].apply(status_badge_html)
display_frame["Status"] = display_frame["Status"].apply(status_indicator)
st.dataframe(
    display_frame[["PID", "Process Name", "CPU Usage %", "Memory Usage %", "CPU Trend Δ", "Memory Trend Δ", "Consistency Score", "Status"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "CPU Usage %": st.column_config.NumberColumn(format="%.2f"),
        "Memory Usage %": st.column_config.NumberColumn(format="%.2f"),
        "CPU Trend Δ": st.column_config.NumberColumn(format="%.2f"),
        "Memory Trend Δ": st.column_config.NumberColumn(format="%.2f"),
        "Consistency Score": st.column_config.NumberColumn(format="%.2f"),
        "Status": st.column_config.TextColumn("Status"),
    },
)

badge_line = " ".join([status_badge_html(state) for state in ["running", "sleeping", "stopped", "zombie", "other"]])
st.markdown(badge_line, unsafe_allow_html=True)
