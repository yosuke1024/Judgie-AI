# ⚖️ Judgie-AI User Manual

Judgie-AI is an AI-powered project evaluation platform (single-tenant, hosting one project per instance) leveraging Google Gemini's multimodal capabilities. It automatically analyzes team/candidate submissions (source code ZIPs, demo videos, presentation PDFs, resumes) from various professional angles using customizable AI judge personas, providing teams with score breakdowns and actionable coaching feedback.

This manual explains how to use the platform step-by-step for each role (**Admin (Organizer)**, **Team / Participant (Candidate)**, and **Observer (Spectator)**).

---

## 📂 Quick Navigation
- [1. Initial Launch & Login](#1-initial-launch--login)
- [2. 🔐 System Setup & Admin Guide](#2-🔐-system-setup--admin-guide)
- [3. 👑 Project Operation Guide](#3--project-operation-guide)
- [4. 🧑‍💻 Team (Participant / Candidate) Guide](#4--team-participant--candidate-guide)
- [5. 👁️ Observer (Spectator) Guide](#5--observer-spectator-guide)
- [6. ❓ FAQ & Troubleshooting](#6--faq--troubleshooting)

---

## 1. Initial Launch & Login

### How to Launch
Once Judgie-AI is launched, it will open the login page in your browser (default: `http://localhost:5173` or `http://localhost:5173/login`).

### Language Settings
You can switch the UI and AI-generated feedback language at any time using the language switch button (globe icon) on the login page or within the app.

### Authentication Methods
Depending on the server configuration (environment variables), the login method will adapt:
1. **Password Authentication (Default)**
   - Log in using your registered "Email Address" and "Password".
2. **OIDC (Single Sign-On) Authentication**
   - If `OIDC_ENABLED=true` is set, the password input field is hidden for security and user experience. Instead, a **"Sign in with SSO"** button is displayed on the login page.
   - Authenticate via your identity provider (e.g., Google OAuth). You will be logged in automatically based on your verified email address.
   - When OIDC is enabled, password-related settings (such as changing passwords) are hidden throughout the app.

---

## 2. 🔐 System Setup & Admin Guide

The administrator is responsible for initial setup, configuring OIDC (SSO) authentication, and setting up the Gemini API key.

### 2-1. Initial Login & Security Setup
1. On the login page, enter the default admin email and password:
   - **Email:** `admin@example.com` (Default. Customizable via `DEFAULT_ADMIN_EMAIL` env var)
   - **Password:** `admin123` (Default. Customizable via `DEFAULT_ADMIN_PASSWORD` env var)
2. After logging in, navigate to the **"👑 Command Center"** using the top navigation menu.
3. > [!CAUTION]
   > For security reasons, please change the default password immediately using the **"System Settings"** -> **"Change Admin Password"** section.

### 2-2. Configuring OIDC Authentication (SSO)
You can configure Single Sign-On (SSO) in the **"System Settings"** tab, under the **"OIDC Authentication Settings (SSO)"** card.

* **Settings Fields:**
  - **Enable OIDC (SSO) Authentication:** Check this to enable SSO. When active, local team password login is disabled.
  - **Issuer URL:** The identity provider's issuer URL (e.g., `https://accounts.google.com`).
  - **Client ID / Client Secret:** The credentials issued by your identity provider.
  - **Redirect URI:** The callback URL (e.g., `http://localhost:5173/login/callback`). Leave blank to use the default value.
  - **Allowed Email Domains / Allowed Individual Emails:** Restrict access to specific email domains or addresses (comma-separated list). Leave blank to allow any authenticated user.
* **Emergency Login Bypass (Anti-Lockout):**
  If OIDC is misconfigured, the seed administrator accounts (e.g., `admin@example.com`) can still log in locally via the **"Admin Login (Password)"** link at the bottom, using their password. Once logged in, you can update OIDC credentials or turn OIDC off.

---

## 3. 👑 Project Operation Guide

Admins log in using their administrator credentials to set up the evaluation environment, manage AI judges, register teams, and monitor evaluations.

### 3-1. Logging in as Admin
1. Navigate to the login page (`http://localhost:5173/login`).
2. Log in using your email (e.g., `admin@example.com`) and password, then click **"Log In"** (If OIDC is active, you can also log in via SSO, or bypass it using the **"Admin Login (Password)"** link at the bottom).

### 3-2. Setting Up the Project

Once logged in, you can access the **"👑 Admin Command Center"**. Follow these steps to prepare your project:

#### 🚀 Step 1: Select Evaluation Template (Project Setup)
When an admin logs in for the first time, a setup screen forces you to select an **Evaluation Template** (except in demo mode).
Choose one of the pre-built templates or import a custom one:

| Template Name | Target & Description | Initial Context Mode | Default Q&A Turns |
| :--- | :--- | :--- | :--- |
| **Project Evaluation (Hackathon)** | Evaluates prototype completeness, technical implementation, UX, and presentation. | Cumulative (Iterative) | 1 Turn (1 Q&A exchange) |
| **Startup Pitch Review** | Assesses market opportunity, viability, defensibility, and team capability. | Independent (Fresh start) | 3 Turns |
| **Hiring & Technical Interview** | Evaluates candidate coding skills, system design depth, communication, and team fit. | Independent (Fresh start) | 5 Turns |
| **Software Architecture Review** | Audits system design for scalability, reliability, security, and cost efficiency. | Independent (Fresh start) | 0 Turns (Q&A Disabled) |
| **Custom (Import from URL)** | Imports custom criteria and personas from an external JSON file raw URL. | - | - |

- **Importing Custom Templates**:
  - You can define your own template in JSON format and import it by providing the **Raw URL** (e.g., from a GitHub repository: `https://raw.githubusercontent.com/.../template.json`).
  - Allowed domains are restricted to trusted domains (e.g., `github.com`, `raw.githubusercontent.com`) for security reasons.

#### Step 2: System Settings (API Validation & LLM Providers)
- Go to the **"System Settings"** page.
- Under the LLM settings tab (e.g., **"🤖 Gemini Configuration"**), enter your API key and save it.
  - **Multiple LLM Providers**: Judgie-AI supports multiple providers like Google Gemini, OpenAI, and Anthropic.
  - > [!IMPORTANT]
    > Providers other than Gemini (OpenAI, Anthropic) do not support multimodal video analysis. If these providers are selected, the system will automatically block video file uploads (MP4/MOV) on the participant dashboard.

#### Step 3: Configure Evaluation Criteria
- Go to the **"⚖️ Criteria"** tab.
- Add or edit the evaluation criteria. You can assign a **"Weight (%)"** to each criterion, which determines its influence on the 100-point total score.
- **Active / Inactive Toggle**: Use the toggles to temporarily disable a criterion without deleting it. Inactive criteria are excluded from AI evaluations and scoreboard calculations.

#### Step 4: Configure Judges (Personas)
- Go to the **"🧑‍⚖️ AI Judges"** tab.
- Define the professional background and guidelines for each AI judge. Up to **5 active judges** can be configured simultaneously.
- **Custom Avatar Images**: You can upload a custom avatar image (PNG/JPG, max 500KB) for each judge. If configured, it will be rendered as a circular profile photo in the team dashboard and chat bubble instead of the default emoji.
- **Active / Inactive Toggle**: Temporarily disable a judge. Inactive judges will not participate in evaluations or Q&A threads.

#### Step 5: Register Teams/Participants (Team Management)
- Go to the **"🏢 Teams"** tab.
- **Add Individually**:
  - **Default Mode**: Enter the member's `Email`, `Password`, `Team ID`, and choose a **`Role`**.
  - **OIDC Mode**: Enter the member's `Email`, `Team ID`, and choose a **`Role`** (passwords are generated randomly).
- **CSV Bulk Import**: Upload a CSV file to register multiple users at once.
  - CSV Format: Use `email,team_id,role[,display_name][,password]` columns in order.
- **Active / Inactive Toggle**: Toggle the "Active" switch next to any team. Inactive teams are blocked from logging in and hidden from the scoreboard/submissions list.
- **Delete Team/User**: Permanently delete teams and all their related submissions/chat history under the "Delete User/Team" section (Cascading deletion; note that administrator accounts cannot be deleted).

#### Step 6: AI Language Settings
- Go to the **"AI Languages"** tab. Save up to 5 languages for AI evaluation feedback and chats. Teams can switch between these languages via tabs on their dashboards.

#### Step 7: Project Settings
- Go to the **"Project Settings"** tab to tune evaluation behavior (Cumulative vs. Independent context modes) and set the Q&A turn limits.

---

### 3-3. Ongoing Project Management

#### Monitor the Live Scoreboard
- Check the **"Live Scoreboard"** tab for real-time overall scores, team statuses, and consultation counts.

#### Deep Dive & Delete Consultations
- Go to the **"Deep Dive"** tab.
- Review submitted source codes/materials and chat directly with the AI judges about specific submissions.
- **Delete Consultation History**: If a team accidentally submits the wrong file, you can delete that specific submission history. This will delete the evaluation records and chat logs, and **automatically restore one consultation attempt** to the team's balance.

---

## 4. 🧑‍💻 Team (Participant / Candidate) Guide

Teams upload submissions to receive intermediate feedback (AI Consultations) or final evaluations.

### 4-1. Logging In
1. Navigate to the login page (`http://localhost:5173/login`).
2. Log in using email & password or OIDC (SSO) depending on the project settings.

### 4-2. Profile & Password Management
- Update your product name, team name, and one-liner pitch under the **"Team Profile"** section.
- **🔐 Change Password**: Change your password (only available in password mode; hidden in OIDC mode).

### 4-3. Uploading Submissions & AI Consultations

Before final submission, you can request AI evaluations. The remaining attempts are shown on the dashboard.

#### 📁 Supported File Formats
You can submit any combination of the following formats:

1. **Source Code ZIP Archive:**
   - Exclude large folders like `node_modules`, `.git`, or `venv` to avoid the 200MB size limit.
   - Example Command (Mac/Linux): `zip -r submission.zip . -x "node_modules/*" -x ".git/*" -x "venv/*" -x ".next/*"`
2. **Presentation Slides (PDF)**
3. **Demo Video (MP4 / MOV):**
   - > [!WARNING]
     > If the backend is configured with OpenAI or Anthropic (which do not support video analysis), the dashboard will alert you and block submissions containing video files. Please submit only ZIPs or PDFs in this case.

#### Steps to Request Consultation
1. **Upload Files**: Drag & drop or select files in the "Submit Your Work" box.
2. **Submit for AI Consultation**: Click the button. Feedback will be generated in a few minutes, consuming one attempt.

### 4-4. Reviewing Feedback
Once processed, you can view the overall impact score, radar charts, history trends, and detailed criteria breakdowns with judge-specific advice (supports switching language tabs).

### 4-5. "Objection!" & Q&A Chat
If you have questions about the feedback, use the **"🙋 Objection! / Q&A"** section at the bottom of your feedback. Submit questions to start a debate among the AI judges, which may refine your evaluation.

### 4-6. Final Submission
When ready, check the **"Final Submission"** checkbox and click "Submit Final Submission". This locks your scores on the scoreboard and blocks further uploads or chats.

---

## 5. 👁️ Observer (Spectator) Guide

Observers monitor team progress and evaluations in read-only mode.

### 5-1. Logging In
1. Log in via the standard login page.

### 5-2. Read-Only Access
An **"Observer Mode: Read-Only View"** header is displayed, indicating all write/action operations are disabled.

- **Available Views**:
  - **Team Dashboards**: Select any team from the sidebar to inspect their submission history, radar charts, AI feedback, and Q&A logs.
  - **Leaderboard (The Hype Board)**:
    - **🚀 Current Rankings**: View overall scoreboard standings.
    - **🏅 Category Leaders**: Toggle criteria tabs to see top 5 teams per category.
    - **🤖 Meet the AI Jury Panel**: Meet the active AI judges (click "🧠 View Persona" to unfold system prompts).
    - **⚖️ The Rules of the Game**: View all active criteria, weights, and detailed descriptions.

---

## 6. ❓ FAQ & Troubleshooting

#### Q. I got "Account Not Registered" during OIDC login.
- **A.** Your email address must be pre-registered by the Admin in the database. Please ask the organizer to check your registration details.

#### Q. I cannot upload video files and the submit button is locked.
- **A.** The project is likely configured with OpenAI or Anthropic backend models, which do not support video analysis. Please remove video files and submit ZIP or PDF files only.

#### Q. I get a size limit error when uploading a ZIP file.
- **A.** Ensure your ZIP file size is under 200MB. Use the exclusion ZIP command to exclude folders like `node_modules` or `.git`.
