# Contributing to Judgie-AI

First off, thank you for considering contributing to Judgie-AI! We welcome contributions from everyone.

## Code of Conduct

By participating in this project, you are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md).

## How Can I Contribute?

### Reporting Bugs
- Ensure the bug was not already reported by searching on GitHub under Issues.
- If you're unable to find an open issue addressing the problem, open a new one. Be sure to include a title and clear description, as much relevant information as possible, and a code sample or an executable test case demonstrating the expected behavior that is not occurring.

### Suggesting Enhancements
- Open a new issue with a clear title and description.
- Explain why this enhancement would be useful to most users.

### Contributing Evaluation Templates
One of the easiest ways to contribute to Judgie-AI is by adding new evaluation templates (e.g., for design reviews, marketing pitches, coding exams, etc.).

1. Copy the sample file [templates/template.sample.json](templates/template.sample.json) as a reference.
2. Create your new JSON file in the `templates/` directory (e.g., `templates/design_review.json`).
3. Define your evaluation criteria (ensure the sum of all weights equals `100`) and AI judge personas.
4. Run validation tests locally to verify your template's structure:
   ```bash
   pytest tests/test_templates_validation.py
   ```
5. Submit a Pull Request! Once merged, your template will be available as an official template.

### Pull Requests
1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code conforms to the existing style.
6. Issue that pull request!

## Local Development

Please refer to the **Local Development Setup** section in the [README.md](README.md) for detailed, step-by-step instructions on setting up and running the React frontend and FastAPI backend.

Briefly:
1. Start the FastAPI backend server on port 8000.
2. Start the React frontend client (Vite) on port 5173.
3. Log in as `superadmin` (passcode: `superadmin123`) at `http://localhost:5173` to create your evaluation project. Then, log in as the newly created project admin and configure your Gemini API Key in the **System Settings** UI.

## Coding Guidelines
Please refer to the existing code style. We encourage clear variable names, concise functions, and documenting complex logic ("Why" over "What").
