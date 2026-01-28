# 🏥 MedLog Shared Care

MedLog is a collaborative medication adherence platform designed for patients and clinicians. It provides real-time monitoring and high-visibility alerts to ensure medication schedules are followed safely and accurately.



## ✨ Key Features

- **Role-Based Access:** - **Patients:** Log daily doses and view personal history.
  - **Clinicians:** Monitor multiple patients from a single dashboard and log doses on their behalf.
- **The 4-Hour Safety Alert:** Automated system that turns the dashboard status **RED** if no medication has been logged within a 4-hour window.
- **Smart Registration:** A specialized "Add Another User" flow that clears the form automatically, allowing clinicians to set up multiple patient accounts quickly.
- **Audit Trail:** Persistent logging of medication name, dosage, and precise timestamps using a local SQLite database.

## 🛠️ Tech Stack

- **Frontend/UI:** [Streamlit](https://streamlit.io/)
- **Backend:** Python 3.x
- **Database:** SQLite3
- **Deployment:** Streamlit Community Cloud



## 🚀 Local Setup

To run this project on your own machine, follow these steps:

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/CyeCandy/med-tracker.git]