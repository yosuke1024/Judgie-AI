# ⚖️ Judgie-AI

![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.50+-red.svg)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://judgie-ai.streamlit.app)

**Judgie-AI** is a multi-tenant AI hackathon platform that automates and enhances the judging and feedback process. Leveraging Google Gemini's multimodal capabilities, it evaluates team submissions (source code ZIPs, demo videos, PDF slides) from the diverse perspectives of a customizable panel of AI expert personas, providing actionable coaching and scoring.

> 💡 **Judgie-AI** is part of the **[PixApps](https://pixapps.ai/)** suite — a collection of innovative, AI-powered applications. Explore our other projects and support our work at [pixapps.ai](https://pixapps.ai/).

---

## ✨ Core Features

1. **🏢 Multi-tenant Architecture & Administration**
   - Super Admins can create/delete hackathons (tenants) and manage Tenant Admin credentials.
   - Tenant Admins can manage team accounts, including bulk import via CSV, passcode resets, and settings.
   - Each hackathon operates in an isolated database space ensuring secure data separation.
2. **🧑‍⚖️ Customizable AI Persona Panel**
   - Define custom "Criteria" and "Personas" for each hackathon.
   - Multiple AI judges review submissions from distinct professional angles (e.g., UX Designer, VC, Principal Engineer).
   - Support custom avatar images (Base64 encoding) or emojis for each judge.
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
- **AI Core**: Google Gemini API (Supports dynamic model selection: `gemini-3.5-flash`, `gemini-3.1-pro`, `gemini-3.1-flash-lite`, etc.) - Utilizes the File API for asynchronous parsing of large contexts (Code ZIPs, Videos, etc.)

## 📂 Directory Structure

```
├── .github/              # GitHub Actions workflows & PR templates
├── app.py                # Main Streamlit application entry point
├── config.py             # Configuration and constants
├── core/                 # Shared system logic and modules
│   ├── services/         # Business logic layer (evaluations, submissions)
│   ├── auth.py           # Authentication and session logic
│   ├── db.py             # SQLite database operations and models
│   ├── file_handler.py   # File system processing and validation
│   ├── gemini.py         # Google Gemini API integration
│   ├── i18n.py           # Translations and bilingual routing
│   ├── security.py       # Password hashing (bcrypt)
│   └── ui_utils.py       # Reusable Streamlit UI components
├── docs/                 # Documentation (testing guide, user manuals)
├── tests/                # Test suite for db, auth, services, and UI
├── views/                # Streamlit UI pages for different roles
├── requirements.txt      # Production dependencies
└── requirements-dev.txt  # Development dependencies (pytest, ruff)
```

## 🔐 Security Note

> **Note**
> - Team and admin passcodes are safely hashed using `bcrypt` before being stored in the database, protecting credentials from exposure.
> - An optional IP-based firewall is supported via the `ALLOWED_IPS` environment variable (comma-separated IP addresses) to restrict platform access.

## 📦 Setup

### 1. Clone the repository
```bash
git clone https://github.com/yosuke1024/Judgie-AI.git
cd Judgie
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the application
```bash
streamlit run app.py
```

### 4. Initial Login & API Key Configuration
Upon the first launch, a default `superadmin` account is created automatically.
- **Team ID**: `superadmin`
- **Passcode**: `superadmin123`

Log in, go to the "🌍 Super Admin Console", and create a new hackathon. **Please change your password immediately after your first login.**

Once the hackathon is created:
1. Log out and log back in using the newly created **Tenant Admin** credentials.
2. Go to **⚙️ System Settings** -> **🤖 Gemini Configuration** tab.
3. Input and save your **Gemini API Key**. This will dynamically fetch and let you select the available Gemini models.

## 📖 User Manuals

For detailed instructions on how to use the platform as a Participant (Team), Tenant Admin, or Super Admin, please refer to our bilingual user manuals:
- [📖 English User Manual](docs/user_manual_en.md)
- [📖 日本語 ユーザーマニュアル](docs/user_manual_ja.md)

## 🔐 Roles & Access

| Role | Example ID | Primary Responsibilities |
|---|---|---|
| **🌍 Super Admin** | `superadmin` | Create new hackathons, reset admin passwords, manage the system globally. |
| **👑 Hackathon Admin** | (Issued by Super Admin) | Set evaluation criteria, manage personas, register teams, view the live scoreboard. |
| **🧑‍💻 Team (Participant)** | (Issued by Admin) | Upload submissions, request AI coaching, edit profiles, object to judges' feedback. |

---
**Technical Notes:** 
- The SQLite database (`judgie.db`) is automatically created in the `data/` directory upon execution.
- To prevent session loss upon Streamlit reloads, **persistent session management** is implemented via URL query parameters (`?sid=`).
- File Watcher is disabled (`fileWatcherType = "none"`) in `.streamlit/config.toml` to prevent unintended session resets during development.

## 🧪 Testing

Judgie-AI features a comprehensive test suite. For details on how to run tests locally and verify code coverage, please refer to [docs/testing.md](docs/testing.md).

## 🤝 Contributing

We welcome contributions from the community! Please read our [CONTRIBUTING.md](CONTRIBUTING.md) to learn how to get started, set up your development environment, and submit pull requests.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.
