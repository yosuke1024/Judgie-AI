# ⚖️ Judgie-AI

![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red.svg)

**Judgie-AI** is a multi-tenant AI hackathon platform that automates and enhances the judging and feedback process. Leveraging Google Gemini's multimodal capabilities, it evaluates team submissions (source code ZIPs, demo videos, PDF slides) from the diverse perspectives of a customizable panel of AI expert personas, providing actionable coaching and scoring.

---

## ✨ Core Features

1. **🏢 Multi-tenant Architecture**
   - Super Admins can create multiple hackathons (tenants) and issue dedicated Tenant Admin accounts.
   - Each hackathon operates in an isolated database space ensuring secure data separation.
2. **🧑‍⚖️ Customizable AI Persona Panel**
   - Define custom "Criteria" and "Personas" for each hackathon.
   - Multiple AI judges review submissions from distinct professional angles (e.g., UX Designer, VC, Principal Engineer).
   - Dynamically toggle active judges from the admin dashboard.
3. **📈 Iterative Coaching**
   - Teams can receive "AI Consultations" up to 3 times before final submission.
   - Dashboards visualize score histories and progress deltas to boost team motivation.
4. **🙋 Objection / Q&A ("Objection!" Feature)**
   - Teams can object to or ask questions about the AI's evaluation once per consultation.
   - The AI panel holds a "debate" based on previous context to respond, providing an engaging and convincing UX.
5. **💬 Admin Submission Chat**
   - Hackathon admins can directly chat with the AI panel about a team's submission (e.g., "What tech stack are they using?", "Any security concerns?").
6. **🌐 Bilingual UI**
   - Seamless English/Japanese switching. AI feedback and summaries are generated in both languages simultaneously.

## 🚀 Tech Stack

- **Frontend & Backend**: Streamlit (Python)
- **Database**: SQLite3
- **AI Core**: Google Gemini (gemini-2.5-flash) - Utilizes the File API for asynchronous parsing of large contexts (Code ZIPs, Videos, etc.)

## 📂 Directory Structure

```
├── app.py                # Main Streamlit application entry point
├── config.py             # Configuration and constants
├── core/
│   ├── auth.py           # Authentication logic
│   ├── db.py             # SQLite database operations
│   └── gemini.py         # AI integration and file processing
├── personas/             # AI Persona prompt definitions (.md)
├── views/                # Streamlit UI pages for different roles
└── requirements.txt      # Python dependencies
```

## 🔐 Security Note for Production

> **Warning**
> This project was developed as a rapid prototype for a hackathon. In the current MVP version, **team passcodes and admin passcodes are stored in plaintext in the SQLite database** for simplicity. 
> 
> If you plan to use this in a production environment or over the public internet, it is strongly recommended to implement password hashing (e.g., using `bcrypt` or `argon2`) in `core/db.py` before deployment.

## 📦 Setup

### 1. Clone the repository
```bash
git clone https://github.com/moneyforward/judgie-ai.git
cd Judgie
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Set your Gemini API key in the `.env` file (if you are running the platform locally) or set it via the Admin UI later.
```env
GEMINI_API_KEY=your_api_key_here
```

### 4. Run the application
```bash
streamlit run app.py
```

### 5. Initial Login
Upon the first launch, a default `superadmin` account is created automatically.
- **Team ID**: `superadmin`
- **Passcode**: `superadmin123`

Log in, go to the "🌍 Super Admin Console", and create a new hackathon. **Please change your password immediately after your first login.**

## 🔐 Roles & Access

| Role | Example ID | Primary Responsibilities |
|---|---|---|
| **🌍 Super Admin** | `superadmin` | Create new hackathons, reset admin passwords, manage the system globally. |
| **👑 Hackathon Admin** | (Issued by Super Admin) | Set evaluation criteria, manage personas, register teams, view the live scoreboard. |
| **🧑‍💻 Team (Participant)** | (Issued by Admin) | Upload submissions, request AI coaching, edit profiles, object to judges' feedback. |

---
**Technical Notes:** 
- The SQLite database (`judgie.db`) is automatically created in the root directory upon execution.
- To prevent session loss upon Streamlit reloads, **persistent session management** is implemented via URL query parameters (`?sid=`).
- File Watcher is disabled (`fileWatcherType = "none"`) in `.streamlit/config.toml` to prevent unintended session resets during development.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
