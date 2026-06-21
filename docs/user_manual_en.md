# ⚖️ Judgie-AI User Manual

Judgie-AI is an AI-powered project evaluation platform (multi-tenant) leveraging Google Gemini's multimodal capabilities. It automatically analyzes team/candidate submissions (source code ZIPs, demo videos, presentation PDFs, resumes) from various professional angles using customizable AI judge personas, providing teams with score breakdowns and actionable coaching feedback.

This manual explains how to use the platform step-by-step for each role (**Super Admin**, **Project Admin (Organizer)**, **Team / Participant (Candidate)**, and **Observer (Spectator)**).

---

## 📂 Quick Navigation
- [1. Initial Launch & Login](#1-initial-launch--login)
- [2. 🌍 Super Admin (Global Administrator) Guide](#2--super-admin-global-administrator-guide)
- [3. 👑 Project Admin (Organizer) Guide](#3--project-admin-organizer-guide)
- [4. 🧑‍💻 Team (Participant / Candidate) Guide](#4--team-participant--candidate-guide)
- [5. 👁️ Observer (Spectator) Guide](#5--observer-spectator-guide)
- [6. ❓ FAQ & Troubleshooting](#6--faq--troubleshooting)

---

## 1. Initial Launch & Login

### How to Launch
Once Judgie-AI is launched, it will open the login page in your browser (default: `http://localhost:5173` or `http://localhost:5173/login`).

### Language Settings
You can switch the UI and AI-generated feedback language at any time using the language switch button (globe icon) on the login page or within the app.

### ✨ Demo Experience Mode
You can try Judgie-AI immediately without credentials or Gemini API keys.
Under the "✨ Demo Experience" section on the login page, you can log in with:
- **Try as Team (Participant)**: User ID `demo_team` / Passcode `demo123`
- **Try as Admin (Host)**: User ID `demo_admin` / Passcode `demo123`
- > [!NOTE]
  > Demo Mode (Project ID: 9999) is a secure **Read-only** mode. Uploading files, triggering evaluations, adding users, or changing settings are disabled. Please explore the pre-loaded feedback history and debate history.

---

## 2. 🌍 Super Admin (Global Administrator) Guide

The Super Admin is responsible for global system management, creating new projects (tenants), and issuing project administrator accounts.

### 2-1. Initial Login & Security Setup
1. Click the **"🌍 Super Admin Login"** link at the bottom of the login page to navigate to the Super Admin login screen.
2. Log in using the default credentials:
   - **Super Admin ID:** `superadmin`
   - **Passcode:** `superadmin123`
3. After logging in, you will see the **"🌍 Super Admin Console"**.
4. > [!CAUTION]
   > For security reasons, please change the default passcode immediately using the **"Change Password"** section.

### 2-2. Creating a New Project (Tenant)
1. Go to the **"Create New Project"** form.
2. Enter the following information:
   - **Project Name:** e.g., "Summer AI Project 2026"
   - **Tenant Admin ID:** e.g., `admin`
   - **Tenant Admin Password:** The password the Project Admin will use to log in.
3. Click the **"Create Project"** button. This creates a fully isolated database partition for the new tenant.

### 2-3. Tenant Management & Deletion
1. From the registered projects list, you can reset tenant admin passwords or delete projects.
2. > [!WARNING]
   > Deleting a project will permanently erase all associated teams, submissions, and AI evaluation logs. This action is irreversible.

---

## 3. 👑 Project Admin (Organizer) Guide

Project Admins log in using the accounts provided by the Super Admin. They configure project settings, select evaluation templates, manage AI judges, register teams/participants, and monitor submissions.

### 3-1. Logging in as Project Admin
1. Navigate to the login page (`http://localhost:5173/login`).
2. Select your project from the **"Select Project"** dropdown.
3. Enter your **"Team ID / Admin ID"** (e.g., `admin`) and **"Passcode"**, then click **"Log In"**.

### 3-2. Setting Up the Project

Once logged in, you can access the **"👑 Admin Command Center"**. Follow these steps to prepare your project:

#### 🚀 Step 1: Select Evaluation Template (Project Setup)
When an admin logs in for the first time, a setup screen forces you to select an **Evaluation Template** (except in demo mode).
Choose one of the pre-built templates or import a custom one:

| Template Name | Target & Description | Initial Context Mode | Default Q&A Turns |
| :--- | :--- | :--- | :--- |
| **Project Evaluation (Hackathon)** | Evaluates prototype completeness, technical implementation, UX, and presentation. | Cumulative (Iterative) | 1 Turn (1 Q&A exchange) |
| **Startup Pitch Review** | Assesses market opportunity, business model viability, defensibility, and team capability. | Independent (Fresh start) | 3 Turns |
| **Hiring & Technical Interview** | Evaluates candidate coding skills, system design depth, communication, and team fit. | Independent (Fresh start) | 5 Turns |
| **Software Architecture Review** | Audits system design for scalability, reliability, security, and cost efficiency. | Independent (Fresh start) | 0 Turns (Q&A Disabled) |
| **Custom (Import from URL)** | Imports custom criteria and personas from an external JSON file raw URL. | - | - |

- **Importing Custom Templates**:
  - You can define your own template in JSON format and import it by providing the **Raw URL** (e.g., from a GitHub repository: `https://raw.githubusercontent.com/.../template.json`).
  - Allowed domains for custom templates are restricted to trusted domains (e.g., `github.com`, `raw.githubusercontent.com`) for security reasons.

#### Step 2: System Settings (API Validation & Model Selection)
- Go to the **"System Settings"** page.
- Under the **"🤖 Gemini Configuration"** tab, enter your `Gemini API Key` and click **"Save & Validate API Key"**.
  - The system will test the key and dynamically load the available models.
- After validation succeeds, configure the **Model & Plan Settings**:
  - **Plan Type:** Select your API key plan (Free Tier / Paid Tier). Guidance will display based on your selection.
  - **Model Selection:** Select your preferred model from the dynamically loaded list (e.g., `gemini-3.5-flash` or `gemini-3.1-pro`).
  - > [!IMPORTANT]
    > To avoid Rate Limit issues during actual project reviews, we strongly recommend using a **Paid Tier (Pay-as-you-go)** key. For Free Tier keys, stick to `gemini-3.5-flash` or `gemini-3.1-flash-lite`.

#### Step 3: Configure Evaluation Criteria
- Go to the **"⚖️ Evaluation Criteria"** tab.
- Register/edit criteria that the AI judges will use to score submissions on a scale of 1 to 5.
- Assign a **"Weight (%)"** to each criterion. The weighted average will calculate the 100-point total score.

#### Step 4: Manage Judges (Personas)
- Go to the **"🧑‍🏫 Judges (Personas)"** tab.
- Create and edit AI expert personas (e.g., UX Designer, VC, Principal Engineer).
- You can have **up to 5 active judges** participating in evaluations at the same time.
- Custom avatar images (PNG/JPG, max 500KB) can be uploaded.

#### Step 5: Register Teams & Participants (Team Management)
- Go to the **"🏢 Team Management"** tab to register general participants (`team`) or read-only users (`observer`).
- **Manual Registration:** Add users individually, specifying their ID, passcode, and **`Role`**.
- **Bulk Import (CSV):** Upload a CSV file structured as `team_id, passcode, role` (the 3rd column can be `observer` or `team`. If omitted, it defaults to `team`).
- Distribute the credentials to the registered users.

#### Step 6: Configure AI Response Languages
- Go to the **"🤖 AI Response Settings"** tab.
- Configure up to 5 languages (e.g., English, Japanese) that the AI judges will use to write feedback, action items, and Q&A responses.
- > [!WARNING]
  > Specifying multiple response languages increases AI text generation, which prolongs response latency. We recommend setting only 1 or 2 essential languages.

#### Step 7: Project Behavior & Details (Project Settings)
- Go to the **"⚙️ Project Settings"** tab to fine-tune project behaviors and constraints.
- **🔄 Re-evaluation Context Mode**:
  - **Cumulative**: When teams resubmit, the AI panel reviews the changes by referencing the previous feedback context (Recommended for iterative projects).
  - **Independent**: Evaluates each submission freshly from scratch, ignoring previous feedback history (Recommended for hiring/recruiting and single-run audits).
- **🙋 Max Q&A Dialogue Turns**:
  - Sets how many question/objection exchanges a participant can have with the AI panel (Disable Q&A, 1–5 turns, or Unlimited).

### 3-3. Operations During the Project

#### Monitoring Progress & Live Scoreboard
- Use the **"📊 Live Scoreboard"** tab to view teams' total scores, tie-breaker impact scores, and the number of AI consultations they have used.

#### Submissions & Admin-AI Chat
- Go to the **"💬 Submissions & AI Chat"** tab.
- Select a team and one of their submission histories.
- You can chat directly with the AI judges about the team's actual source code.
  - *Example: "What is the biggest architectural bottleneck in their code?", "Are there any obvious security vulnerabilities?"*
  - This allows organizers to evaluate technical complexity and verify implementation authenticity.

---

## 4. 🧑‍💻 Team (Participant / Candidate) Guide

Participants log in to manage their profiles, upload project files, request intermediate AI coaching (Consultations), and perform final submissions.

### 4-1. Logging in as a Team
1. Go to the login page (`http://localhost:5173` or `http://localhost:5173/login`).
2. Select your project from the **"Select Project"** dropdown.
3. Log in with the **"Team ID"** and **"Passcode"** provided by the organizer.

### 4-2. Profile & Password Management
- Use the **"Team Profile"** panel to update your product name (Product Name), team name (Team Name), and catchphrase (One-liner Pitch). Click "Save" to save your profile.
- Use **"🔐 Change Password"** to update your passcode.

### 4-3. Uploading Artifacts & Requesting AI Coaching (AI Consultation)

Teams can request intermediate feedback from the AI judges before final submission.
- The remaining consultations count is shown in "Consultations Left" (the system default is **up to 3 times**).

#### 📁 Supported Submission Formats & AI Processing
The platform supports the following file types. You can submit **any combination of these files** depending on the nature of your project (e.g., standard coding project, slide-based proposal, video pitch, or resume review).
Source code ZIP is not mandatory—you can submit only PDF slides and demo videos if needed.

1. **Source Code & Text Documents (ZIP):**
   - Typically used for source code repositories and text docs.
   - When uploaded, the system automatically extracts all readable text and sends it to the AI judges as text context.
   - > [!TIP]
     > Exclude large dependencies and administrative folders like `node_modules`, `.git`, or `venv` to prevent exceeding the 200MB size limit or AI context limits.
     > Command example (Mac/Linux): `zip -r submission.zip . -x "node_modules/*" -x ".git/*" -x "venv/*" -x ".next/*"`
2. **Presentation Slides & Documents (PDF):**
   - Used for pitch decks, design wireframes, resumes, or specification documents.
   - Leveraging Gemini's document understanding, the layout, images, and text of the PDF are parsed and evaluated directly.
3. **Product Demo Videos (MP4 / MOV):**
   - Used to show working features, UI transitions, or a recorded presentation pitch.
   - Leveraging Gemini's multimodal video understanding, the AI judges will directly watch and evaluate the UX flow and working logic.

#### Steps to Request Coaching
1. **Upload Files:**
   - Drag and drop your files into the "Submit Your Work" uploader area. You can upload multiple files at once.
2. **Request Coaching:**
   - Click **"Submit for AI Consultation"**. The AI judges will analyze your files and generate feedback in a few minutes, consuming one consultation count.

### 4-4. Reviewing Feedback & Scores

Once analysis is complete, your results will appear on the **"Evaluation Results"** panel.

- **OVERALL IMPACT SCORE:** A weighted score scaled out of 100.
- **Evaluation Balance (Radar):** A radar chart visualizing individual criteria scores (out of 5.0).
- **Score Trend (Max 100):** A line chart visualizing your score improvement over time (you can switch between past consultation records using the "History" dropdown on the top right).
- **Criteria Breakdown (Left Panel):** Lists individual criteria scores and contributions to the overall score.
- **AI Summary:** A concise AI-generated summary of your product and submission.
- **AI Judges Feedback:** Individual reviews from each active AI judge, written in their unique persona's tone.
  - *Note: If multiple response languages are configured, tabs for each language will appear within each feedback section.*

### 4-5. Raising an Objection / Q&A ("Objection!")
For each evaluation, teams can submit questions or objections to the AI panel up to the turn limit configured by the administrator (default is 1 turn).

1. Scroll to the **"🙋 Objection! / Q&A"** section at the bottom.
2. Enter your message or counterargument and click **"Send Message ✊"**.
3. The AI judges will hold a panel debate using the submission context and provide a unified response. In some cases, the judges may adjust their evaluation.

### 4-6. Final Submission
When your product/assignment is complete and ready for final grading, upload your latest files, check the **"Final Submission"** checkbox, and click the **"Submit Final Submission"** button.
- After submitting your final pitch, you can no longer modify submissions or request AI coaching.
- Your final score will be locked and shown on the organizer's scoreboard.

---

## 5. 👁️ Observer (Spectator) Guide

Observers (spectators) log in using the accounts provided by the project administrator to securely monitor and view the progress and scoreboards of each team in the project.

### 5-1. Logging in as an Observer
1. Navigate to the login page (`http://localhost:5173/login`).
2. Select the target project from the **"Select Project"** dropdown.
3. Log in with the **"Observer ID"** and **"Passcode"** provided by the organizer.

### 5-2. Access Scope and Read-Only Restrictions
Once logged in, Observers access a dashboard similar to the Participant UI, but the top displays **"Observer Mode: Read-Only View"**, restricting all editing or submission actions.

- **Available Information**:
  - **Browse Team Dashboards:** Select any team from the left sidebar navigation menu (under the "TEAM DASHBOARDS" section) to view their submission history, AI scores, feedback breakdowns, and Objection debate logs.
  - **Browse Leaderboard:** View the real-time rank of all teams, their total scores, impact metrics, and used consultations. You can also view category-specific leaders under the Category Leaders tabs.
- **Restricted Actions (Write-Disabled)**:
  - Save Team Profile details.
  - Change Passcode.
  - Upload submission files.
  - Request coaching (Submit for AI Consultation).
  - Send Q&A/Objections messages (Send Message).
  - Submit Final Pitch (Final Submission).

---

## 6. ❓ FAQ & Troubleshooting

#### Q: The ZIP file fails to upload.
- **A:** Ensure the total upload size is under 200MB. Make sure you excluded heavy folders like `node_modules` or local python environments (`venv`) from your ZIP archive.

#### Q: Some source files seem to be ignored by the AI, or the AI is hallucinating about the code structure.
- **A:** To prevent exceeding AI token and context limitations, Judgie-AI restricts the total text characters extracted from the ZIP to **800,000 characters** (approx. 200,000 tokens). If the source code exceeds this limit, the system truncates the excess text and appends a `[SYSTEM WARNING: Codebase too large...]` warning. Please exclude non-essential files, media, and heavy library dependencies from your ZIP.

#### Q: The AI coaching takes a long time to respond.
- **A:** Large source code ZIPs and video files can take 1–3 minutes for the Gemini API to analyze. Please keep your browser tab open until the "Processing..." state completes.

#### Q: I cannot log in with the default Super Admin passcode `superadmin123`.
- **A:** Another administrator may have already changed the default password. If the password was lost, a database reset or server administrator intervention may be required.

#### Q: The AI's feedback seems to hallucinate or misinterpret my code.
- **A:** If the uploaded ZIP is corrupted or structured in an unusual way, the AI may fail to locate files. Ensure your main source files (e.g. `app.js`, `main.py`) are placed at or near the root of the ZIP file.
