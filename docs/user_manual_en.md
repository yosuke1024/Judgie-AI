# ⚖️ Judgie-AI User Manual

Judgie-AI is an AI-powered hackathon evaluation platform leveraging Google Gemini's multimodal capabilities. It automatically analyzes team submissions (source code ZIPs, demo videos, presentation PDFs) from various professional angles using customizable AI judge personas, providing teams with score breakdowns and actionable feedback.

This manual explains how to use the platform step-by-step for each role (**Super Admin**, **Hackathon Admin**, and **Team / Participant**).

---

## 📂 Quick Navigation
- [1. Initial Launch & Login](#1-initial-launch--login)
- [2. 🌍 Super Admin (Global Administrator) Guide](#2--super-admin-global-administrator-guide)
- [3. 👑 Hackathon Admin (Organizer) Guide](#3--hackathon-admin-organizer-guide)
- [4. 🧑‍💻 Team (Participant) Guide](#4--team-participant-guide)
- [5. ❓ FAQ & Troubleshooting](#5--faq--troubleshooting)

---

## 1. Initial Launch & Login

### How to Launch
Once Judgie-AI is deployed or run locally, it will open the login page in your browser (default: `http://localhost:8501`).

### Language Settings
You can switch the UI and AI-generated feedback language (**English / 日本語**) at any time using the **"Language / 言語"** radio buttons at the top of the left sidebar.

---

## 2. 🌍 Super Admin (Global Administrator) Guide

The Super Admin is responsible for global system management, creating new hackathons (tenants), and issuing administrator accounts.

### 2-1. Initial Login & Security Setup
1. Add the `?admin=true` parameter to the URL to access the Super Admin login screen (e.g., `http://localhost:8501/?admin=true`).
2. Log in using the default credentials:
   - **Super Admin ID:** `superadmin`
   - **Passcode:** `superadmin123`
3. After logging in, you will see the **"🌍 Super Admin Console"**.
4. > [!CAUTION]
   > For security reasons, please change the default passcode immediately using the **"Change Password"** section.

### 2-2. Creating a New Hackathon (Tenant)
1. Go to the **"Create New Hackathon"** form.
2. Enter the following information:
   - **Hackathon Name:** e.g., "Summer AI Hackathon 2026"
   - **Admin User ID:** e.g., `admin`
   - **Admin Passcode:** The password the Hackathon Admin will use to log in.
3. Click the **"Create Hackathon"** button. This creates a fully isolated database partition for the new tenant.

### 2-3. Tenant Management & Deletion
1. From the registered hackathons list, you can reset tenant admin passwords or delete hackathons.
2. > [!WARNING]
   > Deleting a hackathon will permanently erase all associated teams, submissions, and AI evaluation logs. This action is irreversible.

---

## 3. 👑 Hackathon Admin (Organizer) Guide

Hackathon Admins log in using the accounts provided by the Super Admin. They configure the hackathon rules, set evaluation criteria, manage AI judges, register teams, and monitor live submissions.

### 3-1. Logging in as Hackathon Admin
1. Navigate to the login page (`http://localhost:8501`).
2. Select your hackathon from the **"Select Hackathon"** dropdown.
3. Enter your **"Team ID / Admin ID"** (e.g., `admin`) and **"Passcode"**, then click **"Log In"**.

### 3-2. Setting Up the Hackathon

Once logged in, you can access the **"👑 Admin Command Center"**. Follow these steps to prepare your hackathon:

#### Step 1: System Settings (API Validation & Model Selection)
- Go to the **"System Settings"** page.
- Under the **"🤖 Gemini Configuration"** tab, enter your `Gemini API Key` and click **"Save & Validate API Key"**.
  - The system will test the connection using the key and dynamically fetch the currently available models. An error will display if the key is invalid.
- After validation succeeds, the **"Model & Plan Settings"** section will appear.
  - **Plan Type:** Select your API key plan (Free Tier / Paid Tier). Guidance will display based on your selection.
  - **Model Selection:** Select your preferred model from the dynamically loaded list (e.g. `gemini-3.5-flash` or `gemini-3.1-pro`) and save.
  - > [!IMPORTANT]
    > To avoid Rate Limit quota issues during actual hackathons, we strongly recommend using a **Paid Tier (Pay-as-you-go)** key. For Free Tier keys, please stick to `gemini-3.5-flash` or `gemini-3.1-flash-lite`.

#### Step 2: Configure Evaluation Criteria
- Go to the **"⚖️ Evaluation Criteria"** tab.
- Register criteria that the AI judges will use to score submissions on a scale of 1 to 5 (e.g., `Technical Innovation`, `Business Viability`, `UI/UX Completeness`).
- Assign a **"Weight (%)"** to each criterion. The weighted average will calculate the 100-point total score.
- In the **"Detailed Description"** field, provide thorough scoring instructions for the AI.

#### Step 3: Manage Judges (Personas)
- Go to the **"🧑‍🏫 Judges (Personas)"** tab.
- You can create and edit AI expert personas (e.g., UX Designer, Venture Capitalist, Principal Engineer).
- You can have **up to 5 active judges** participating in evaluations at the same time. Toggle active status using the checkboxes.
- Define each judge's role, background, tone of voice, and focus areas in their prompt definition. You can also upload a custom avatar image (PNG/JPG, max 500KB).

#### Step 4: Register Teams
- Go to the **"🏢 Team Management"** tab.
- **Bulk Import (CSV):** Upload a CSV file structured as `team_id, passcode` to register multiple teams at once.
- **Manual Registration:** Add teams individually using the manual form.
- Distribute the credentials (Hackathon ID, Team ID, Passcode) to each participating team.

### 3-3. Operations During the Hackathon

#### Monitoring Progress & Live Scoreboard
- Use the **"📊 Live Scoreboard"** tab to view teams' total scores, tie-breaker impact scores, and the number of AI consultations they have used.

#### Submissions & Admin-AI Chat
- Go to the **"💬 Submissions & AI Chat"** tab.
- Select a team and one of their submission histories.
- You can chat directly with the AI judges about the team's actual source code.
  - *Example Questions: "What is the biggest architectural bottleneck in their code?", "What backend framework are they using?", "Are there any obvious security vulnerabilities?"*
  - This allows organizers to evaluate technical complexity and verify implementation authenticity.

---

## 4. 🧑‍💻 Team (Participant) Guide

Teams log in to manage their profiles, upload project files, request intermediate AI coaching (Consultations), and perform final submissions.

### 4-1. Logging in as a Team
1. Go to the login page (`http://localhost:8501`).
2. Select your hackathon from the **"Select Hackathon"** dropdown.
3. Log in with the **"Team ID"** and **"Passcode"** provided by the organizer.

### 4-2. Profile & Password Management
- Click **"⚙️ Edit Profile"** under the **"📤 Submission"** header to update your product name, team name, and product catchphrase (One-liner).
- Use **"🔐 Change Password"** to update your passcode.

### 4-3. Uploading Artifacts & Requesting AI Coaching

Teams can request intermediate feedback from the AI judges **up to 3 times** before final submission.

#### 📁 Supported Submission Formats & AI Processing
The platform supports the following file types. You can submit **any combination of these files** depending on the nature of your hackathon (e.g., standard coding hackathon, non-coding ideathon, no-code prototyping). Source code ZIP is not mandatory—you can submit only PDF slides and demo videos if needed.

1. **Source Code & Text Documents (ZIP):**
   - Typically used for source code repositories and text docs.
   - When uploaded, the system automatically extracts all readable text and sends it to the AI judges as text context.
   - > [!TIP]
     > Exclude large dependencies and administrative folders like `node_modules`, `.git`, or `venv` to prevent exceeding the 200MB size limit or AI context limits.
     > Command example (Mac/Linux): `zip -r submission.zip . -x "node_modules/*" -x ".git/*" -x "venv/*"`
2. **Presentation Slides & Documents (PDF):**
   - Used for pitch decks, design wireframes, and business specifications.
   - Leveraging Gemini's document understanding, the layout, images, and text of the PDF are parsed and evaluated directly.
3. **Product Demo Videos (MP4 / MOV):**
   - Used to show working features, UI transitions, or a recorded presentation pitch.
   - Leveraging Gemini's multimodal video understanding, the AI judges will directly watch and evaluate the UX flow and working logic.

#### Steps to Request Coaching
1. **Upload Files:**
   - Drag and drop your files into the "Artifacts (ZIP, MP4, MOV, PDF)" file uploader area. You can upload multiple files at once.
2. **Request Coaching:**
   - Click **"Get AI Coaching"**. The AI judges will analyze your files and generate feedback in a few minutes, consuming one consultation count.

### 4-4. Reviewing Feedback & Scores

Once analysis is complete, your results will appear on the **"💬 AI Feedback Dashboard"**.

- **Total Score:** A weighted score scaled out of 100.
- **Score Breakdown:** Individual criteria scores (out of 5.0) and score changes (deltas) from your previous consultation.
- **Score History & Radar Charts:** Visual representations of your project's improvements over time.
- **Feedback Tabs:**
  - **Top Priorities (Next Steps):** Specific action items suggested by the AI to improve your product.
  - **AI Product Understanding:** A summary of how the AI understands your project.
  - **Judges Feedback:** Individual reviews from each active AI judge, written in their unique persona's tone.

### 4-5. Raising an Objection / Q&A ("Objection!")
For each evaluation, teams can submit **one objection or question** to the AI panel.

1. Scroll to the **"🙋 Objection! / Q&A"** section at the bottom.
2. Enter your message or counterargument and click **"Objection! ✊"**.
3. The AI judges will hold a panel debate using the submission context and provide a unified response. In some cases, the judges may adjust their evaluation.

### 4-6. Final Submission
When your product is complete and ready for final grading, upload your latest files and click **"Submit Final Pitch"**.
- After submitting your final pitch, you can no longer modify submissions or request AI coaching.
- Your final score will be locked and shown on the organizer's scoreboard.

---

## 5. ❓ FAQ & Troubleshooting

#### Q: The ZIP file fails to upload.
- **A:** Ensure the total upload size is under 200MB. Make sure you excluded heavy folders like `node_modules` or local python environments (`venv`) from your ZIP archive.

#### Q: The AI coaching takes a long time to respond.
- **A:** Large source code ZIPs and video files can take 1–3 minutes for the Gemini API to analyze. Please keep your browser tab open until the "Processing..." state completes.

#### Q: I cannot log in with the default Super Admin passcode `superadmin123`.
- **A:** Another administrator may have already changed the default password. If the password was lost, a database reset or server administrator intervention may be required.

#### Q: The AI's feedback seems to hallucinate or misinterpret my code.
- **A:** If the uploaded ZIP is corrupted or structured in an unusual way, the AI may fail to locate files. Ensure your main source files (e.g. `app.js`, `main.py`) are placed at or near the root of the ZIP file.
