# ShareHarvest

**Good Food. Shared with Purpose.**

ShareHarvest is a food redistribution platform that helps restaurants, malls, caterers, and event organizers share surplus food with charities and community organizations.

The goal is to reduce food waste and make food donation easier to coordinate and track.

> **Current stage:** Initial development setup  
> **Database:** SQLite for local development  
> **Docker and PostgreSQL:** Planned for a later stage

---

## 1. Technology Stack

| Part | Technology | Purpose |
|---|---|---|
| Frontend | React + Vite | User interface |
| Backend | Python + Django REST Framework | API and application logic |
| Database | SQLite | Stores local development data |
| Version control | Git | Tracks code changes |
| Future deployment | Docker + PostgreSQL | Containerized, production-oriented setup |

## 2. Current Features

The application currently includes:

- A React + Vite frontend and Django REST Framework API.
- Session authentication, role checks, organization membership, and verification.
- Donation listings, recipient requests, and transactional allocation workflows.
- Pickup scheduling and tracking for approved allocations, with donor, recipient, and volunteer views.
- A health endpoint at `/api/health/` and a local SQLite development database.

Notifications and impact reporting are not implemented.

## 3. Project Structure

```text
shareharvest-starter/
├── backend/
│   ├── config/
│   │   ├── settings.py       # Django settings and database configuration
│   │   ├── urls.py           # Main API and admin routes
│   │   ├── asgi.py
│   │   └── wsgi.py
│   ├── core/
│   │   ├── views.py          # API health-check view
│   │   └── urls.py           # Core API routes
│   ├── manage.py             # Django management commands
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main React page
│   │   ├── main.jsx          # React entry point
│   │   └── styles.css        # Page styles
│   ├── index.html
│   ├── package.json          # JavaScript dependencies and scripts
│   └── vite.config.js
├── docs/
│   └── BUILD_PLAN.md         # Development roadmap
├── .env.example              # Example environment settings
├── .gitignore
├── docker-compose.yml        # Optional; for later Docker setup
└── README.md
```

The `backend/db.sqlite3` file is created automatically after database migrations. It is local data and should not be committed to Git.

---

## 4. Requirements

Install these tools on Windows:

1. **Python 3.12** — https://www.python.org/downloads/
2. **Node.js LTS** — https://nodejs.org/en/download
3. **Visual Studio Code** — https://code.visualstudio.com/
4. **Git** — https://git-scm.com/downloads (recommended)

You do **not** need to install PostgreSQL or Docker to run this version.

After installation, open the VS Code terminal and check:

```powershell
python --version
node --version
npm --version
git --version
```

If a command is not recognized, check that the relevant tool is installed and restart VS Code.

---

## 5. Run the Backend

### Step 1: Open the project folder

Open the `shareharvest-starter` folder in VS Code.

### Step 2: Open a terminal at the project root

Run:

```powershell
cd backend
```

### Step 3: Create a Python virtual environment

```powershell
python -m venv .venv
```

### Step 4: Activate the virtual environment

In Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt and run:

```bat
.venv\Scripts\activate.bat
```

### Step 5: Install backend dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 6: Create the database tables

```powershell
python manage.py migrate
```

Django creates the SQLite database automatically at:

```text
backend/db.sqlite3
```

You do not need to create this file manually.

### Step 7: Start Django

```powershell
python manage.py runserver
```

Keep this terminal open.

The backend should now be available at:

- API health check: http://127.0.0.1:8000/api/health/
- Django admin: http://127.0.0.1:8000/admin/

---

## 6. Run the Frontend

Keep the backend running. Open a **second terminal** in VS Code.

From the project root, run:

```powershell
cd frontend
npm install
npm run dev
```

Vite will display a local URL. It is normally:

http://localhost:5173

Open that URL in your browser.

On the ShareHarvest page, click **Check API health**. The frontend should contact Django and display the API and database status.

---

## 7. Verify the Setup

### Expected health-check response

Open http://127.0.0.1:8000/api/health/

A successful response looks like this:

```json
{
  "service": "ShareHarvest API",
  "status": "ok",
  "database": "ok"
}
```

### Create a Django administrator (optional)

With the backend terminal running, open a third terminal at the project root:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py createsuperuser
```

Follow the prompts. Then open http://127.0.0.1:8000/admin/ and sign in.

The Django administrator is for backend administration. It is not the final ShareHarvest donor or charity login feature.

---

## 8. Stop the Application

To stop the backend, press `Ctrl+C` in its terminal.

To stop the frontend, press `Ctrl+C` in its terminal.

Your SQLite database remains saved in `backend/db.sqlite3`, so your local database data remains available when you start the application again.

---

## 9. Troubleshooting

### `python` is not recognized

Install Python and select **Add Python to PATH** during installation. Restart VS Code and check `python --version`.

### `npm` is not recognized

Install Node.js LTS, restart VS Code, and check `npm --version`.

### PowerShell blocks virtual-environment activation

Use Command Prompt and run:

```bat
.venv\Scripts\activate.bat
```

### The frontend cannot reach the backend

1. Check that Django is running in the first terminal.
2. Open http://127.0.0.1:8000/api/health/ directly.
3. Check the backend terminal for errors.
4. Confirm that the frontend API URL is `http://localhost:8000/api`.

### The health check reports that the database is unavailable

From the `backend` directory, activate the virtual environment and run:

```powershell
python manage.py migrate
python manage.py runserver
```

Read the backend terminal for any error message.

### Port 8000 or 5173 is already in use

Stop the other application using that port, or configure the relevant development server to use a different port.

---

## 10. Development Roadmap

### Stage 1 — Foundation
- [x] Create the React frontend.
- [x] Create the Django REST Framework backend.
- [x] Configure SQLite for local development.
- [x] Add an API and database health check.
- [ ] Verify the setup on the development computer.

### Stage 2 — Accounts and organizations
- Add user registration and authentication.
- Add donor, recipient, volunteer, and administrator roles.
- Create organization profiles and verification.

### Stage 3 — Food donations
- Allow donors to publish and manage donation listings.
- Store food category, quantity, unit, availability, and pickup deadline.
- Add validation and expiry rules.

### Stage 4 — Requests and allocation
- Allow recipient organizations to request available food.
- Support partial allocation of a donation.
- Prevent approved quantities from exceeding the available amount.
- Add tests for concurrent requests.

### Stage 5 — Pickup and impact
- Implement self-pickup and volunteer/delivery-partner scheduling, assignment, and lifecycle tracking.
- Add notifications (future work; excluded from the Pickup implementation).
- Create impact reports from completed donation records.

### Stage 6 — Production readiness
- Switch to PostgreSQL.
- Test database transactions and concurrent allocation.
- Review security and applicable food-safety requirements.
- Configure Docker, deployment, monitoring, and backups.

---

## 11. Database Plan

SQLite is being used because it is simple to set up and requires no separate database server.

Before ShareHarvest is deployed for real organizations, the plan is to move to PostgreSQL. Donation allocation must be protected by backend validation and database transactions so concurrent requests cannot allocate more food than is available.

Changing database configuration alone does not migrate existing data. Any required data must be transferred and tested before switching databases.

---

## 12. Security Notes

- Do not commit `.env`, passwords, API keys, or private data.
- Do not use development settings for a public production deployment.
- Enforce permissions in the Django backend, not only in the React interface.
- Validate donation quantities, deadlines, and status changes on the server.
- Follow applicable local food-safety and handling requirements before operating a live donation service.

---

## License

No license has been selected yet. Add a `LICENSE` file before publicly distributing the code or accepting external contributions.

---

**ShareHarvest — Good Food. Shared with Purpose.**
