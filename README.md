# FINORA &bull; Smart Personal Financial Operating System

[![FINORA CI](https://github.com/sangyam166-ship-it/Expense-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/sangyam166-ship-it/Expense-tracker/actions/workflows/ci.yml)
![Python 3.11 | 3.12](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?logo=python)
![Django 5.1](https://img.shields.io/badge/Django-5.1-success?logo=django)
![REST API](https://img.shields.io/badge/API-REST%20v1-informational)
![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)

A production-quality, responsive Personal Expense Tracker web application built with **Python**, **Django**, and modern Fintech UI styling. Designed specifically for portfolio demonstration, B.Tech CSE final-year capstone, and placement technical interviews.

---

## 🌟 Key Highlights

- **Real Database-Backed Telemetry:** Zero static mockup numbers. Every KPI, balance card, percentage, chart, filter, and report is computed dynamically from real database records.
- **High-Precision Financial Math:** Built using Python's `Decimal` and Django's `DecimalField(max_digits=12, decimal_places=2)` to eliminate floating-point calculation errors.
- **Premium Fintech Aesthetics:**
  - Color palette: Deep Navy (`#0B0F19`), Electric Blue (`#3B82F6`), Soft Purple (`#8B5CF6`), Emerald Green for Inflow (`#10B981`), Coral Red for Outflow (`#EF4444`), and Amber for Limit Warnings (`#F59E0B`).
  - Selective glassmorphism, responsive cards, and clean typography.
  - Native **Dark & Clean Light Mode** toggle with instant persistent state.
- **3D & Motion Design:**
  - Ambient 3D geometric particle canvas powered by **Three.js** with subtle parallax motion.
  - Cinematic dashboard entrance and animated balance number counters powered by **GSAP**.
  - Respects accessibility settings (`prefers-reduced-motion: reduce`).
- **Data Export & Reporting:**
  - Instant **CSV Export** with active keyword and date filters preserved.
  - Certified **Monthly Financial Statements in PDF** generated dynamically using **ReportLab**.
- **Interactive Visualizations:**
  - Multi-series 6-month cashflow trend (Income vs Expenses) via **Chart.js**.
  - Category-wise expense allocation doughnut chart with custom color legends.
  - Weekly burn velocity line chart.

---

## 🏗️ Technology Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.12, Django 5.1, Django REST Framework |
| **Database** | SQLite (development) & PostgreSQL-ready architecture |
| **PDF Engine** | ReportLab 5.1 |
| **Frontend** | HTML5, CSS3 Custom Fintech Design System, Vanilla ES6+ |
| **Data Visuals** | Chart.js 4.x |
| **Motion & 3D** | GSAP 3.12, Three.js (r128) |
| **Iconography** | Lucide Icons |

---

## 📊 Database Models Architecture

- **`UserProfile`:** Extends Django's `User` with multi-currency preferences (`USD`, `INR`, `EUR`, `GBP`, `CAD`, `AUD`, `JPY`, `SGD`, `AED`), theme preferences, monthly income targets, and avatar storage.
- **`Category`:** Standard default categories (Food & Dining, Shopping, Education, Transport, Entertainment, Healthcare, Bills, Travel, Salary, Freelance, Investments) plus custom user-created categories.
- **`Transaction`:** Itemized ledger records with Decimal amounts, transaction type (`EXPENSE`/`INCOME`), date, payment method, category, and notes.
- **`Budget`:** Monthly overall caps and category-level spending limits with automated threshold warnings (80% Caution, 100% Exceeded).
- **`SavingsGoal`:** Dedicated wealth-building milestones with target dates, current contributions, completion percentage, and celebration notifications.
- **`RecurringTransaction`:** Automated tracking for subscriptions, utilities, and memberships with periodic due-date processing.
- **`Notification`:** Real-time event notifications for budget alerts, goal milestones, and welcome tours.

---

## 🚀 Setup & Installation Guide

### 1. Prerequisites
Ensure you have **Python 3.10+** installed on your system.

### 2. Clone / Open Project
```bash
cd "c:\Users\sangya\Desktop\expense tracker"
```

### 3. Activate Virtual Environment
On Windows (PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```
*(Or on Linux/macOS: `source .venv/bin/activate`)*

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Run Database Migrations
```bash
python manage.py migrate
```

### 6. Populate Demo Data (Optional but Recommended)
A custom Django management command is included to seed 6 months of historical transactions, category budgets, active savings goals, and subscriptions:
```bash
python manage.py seed_demo_data
```
> **Pre-configured Demo Credentials:**
> - **Username:** `demo`
> - **Password:** `finora123`
> - *(Staff/Superuser access enabled)*

### 7. Launch Development Server
```bash
python manage.py runserver
```
Open your browser and navigate to: **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

### 🐳 Run with Docker (Optional)
```bash
docker compose up --build
```

---

## 🔌 RESTful API (v1)

FINORA exposes a authenticated JSON REST API powered by Django REST Framework:

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health/` | Public health probe reporting service and DB connectivity |
| `GET` | `/api/v1/transactions/` | List user transactions with optional `?type=`, `?search=`, `?limit=` |
| `POST` | `/api/v1/transactions/` | Create a new transaction via JSON payload |
| `GET` | `/api/v1/transactions/<id>/` | Retrieve specific transaction details |
| `DELETE` | `/api/v1/transactions/<id>/` | Delete a specific transaction |
| `GET` | `/api/v1/categories/` | List available income & expense categories |
| `GET` | `/api/v1/budgets/` | View current month category budget allocations and spent sums |
| `GET` | `/api/v1/goals/` | List savings goals with progress percentages and remaining amounts |
| `GET` | `/api/charts-data/` | Real-time aggregated dataset for Chart.js interactive charts |

---

## 🧪 Automated Testing

FINORA includes an automated test suite verifying CRUD operations, transaction calculations, user data isolation, budget limits, savings milestones, REST API v1 endpoints, and CSV/PDF generation:

```bash
python manage.py test
```
*Output: `Ran 18 tests ... OK`*

---

## 🛡️ Security & Privacy

- **Strict User Data Isolation:** Multi-tenant query filtering ensures users can only view and modify their own financial records.
- **CSRF Protection:** All forms include Django's cryptographic CSRF tokens.
- **Secure Password Hashing:** Uses Django's PBKDF2 password hasher.
- **Server-side Validation:** Clean error handling preventing negative inputs or invalid calculations.

---

## 📱 Navigation & Features Sitemap

- **`/` or `/dashboard/`** &mdash; Real-time financial telemetry, balance counters, recent transactions, quick modals, and charts.
- **`/transactions/`** &mdash; Full ledger with keyword search, category/method/date filters, sorting, and CSV export.
- **`/expenses/`** &mdash; Dedicated expense management with monthly cost-center breakdowns.
- **`/income/`** &mdash; Dedicated income tracking for salaries, freelance contracts, and investments.
- **`/budgets/`** &mdash; Monthly spending limits, category allocations, buffer indicators, and budget cloning.
- **`/goals/`** &mdash; Wealth target milestones, countdown days, and fund contribution modals.
- **`/recurring/`** &mdash; Subscriptions and periodic obligations tracker with automated processing.
- **`/analytics/`** &mdash; Longitudinal analytics, payment method breakdown, and burn velocity.
- **`/reports/`** &mdash; 12-month statements archive with on-demand **PDF statement downloads**.
- **`/profile/`** &mdash; Account details, currency switcher (`$`, `₹`, `€`, `£`, etc.), theme switcher, and password updates.
