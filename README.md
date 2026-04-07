# Real-Time Process Monitoring Dashboard

A powerful and interactive **real-time system monitoring dashboard** built using Streamlit. This application tracks CPU, memory, disk usage, and running processes, providing live insights along with trend analysis and anomaly detection.

---

## Overview

This dashboard allows users to monitor system performance in real-time with detailed analytics, including process-level insights, usage trends, and intelligent alerts for spikes or unusual behavior.

---

## Features

* **Real-time System Metrics**

  * CPU usage (total + per core)
  * Memory & swap usage
  * Disk usage and I/O stats

* **Live Trend Analysis**

  * CPU & memory usage over time
  * Spike and trend detection using statistical methods

* **Smart Insights**

  * Detects abnormal spikes in CPU/memory
  * Identifies consistently high resource-consuming processes

* **Process Monitoring**

  * View all running processes
  * CPU & memory usage per process
  * Process state classification (running, sleeping, stopped, zombie)

* **Advanced Filtering & Sorting**

  * Search processes by name
  * Filter by process state
  * Sort by CPU, memory, trends, or PID

* **Process Control**

  * Terminate processes safely with confirmation

* **Modern UI**

  * Clean dark-themed dashboard
  * Responsive layout with interactive charts

---

## Tech Stack

* **Frontend/UI**: Streamlit
* **Backend/System Data**: Python
* **Libraries Used**:

  * `psutil` – system and process monitoring
  * `pandas` – data handling
  * `streamlit-autorefresh` – real-time updates

---

## Project Structure

```
project-root/
│── app.py
│── requirements.txt
│── README.md
```

---

## Installation & Setup

1. Clone the repository:

```
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

2. Install dependencies:

```
pip install -r requirements.txt
```

3. Run the application:

```
streamlit run app.py
```

---

## 📊 Key Functionalities

* Tracks system-level metrics in real-time
* Maintains historical data for trend detection
* Uses statistical techniques (mean & standard deviation) to detect anomalies
* Displays top processes based on resource usage
* Highlights consistently high resource-consuming processes

---

## Challenges Faced

* Handling real-time updates efficiently without performance lag
* Managing process-level data dynamically
* Implementing accurate spike and trend detection
* Designing a responsive and visually appealing UI in Streamlit

---

## Future Improvements

* Add user authentication
* Deploy on cloud (Streamlit Cloud / AWS / Render)
* Store historical data for long-term analysis
* Add notification system for critical alerts
* Improve visualization with more advanced charts

---

## 👩‍💻 Author

**Kashika**
