# Contributing to FINORA

Thank you for your interest in improving FINORA. Follow these guidelines to contribute effectively:

## Getting Started

1. Fork the repository and create a feature branch (`git checkout -b feature/my-enhancement`).
2. Set up your Python virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Or on Windows: .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Run initial database migrations and verification:
   ```bash
   python manage.py migrate
   python manage.py check
   ```

## Development Guidelines

- **Financial Precision:** Always use `Decimal` for currency and financial calculations; avoid floating-point math for money values.
- **Data Isolation:** Ensure queries filter by `user=request.user` to prevent cross-account access.
- **Testing:** Add test cases in `tracker/tests.py` for any new endpoints, forms, or computation logic.
- **Run Tests:** Ensure all tests pass before submitting changes:
   ```bash
   python manage.py test
   ```

## Pull Request Submission

- Open a PR against the `main` branch.
- Complete the PR template checklist.
- Verify that the GitHub Actions CI pipeline passes.
