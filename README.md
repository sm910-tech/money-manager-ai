# Money Manager AI

An AI-powered personal finance management platform built with **React + Vite + Tailwind CSS + Recharts**, **Python + FastAPI + Pandas**, **Google Gemini API (`google-genai`)**, and **Firebase Authentication + Cloud Firestore**, engineered for **Firebase Hosting** and **Google Cloud Run**.

---

## Key Features

- **Multi-Bank CSV Statement Ingestion:** Parses SBI, HDFC, ICICI, and generic bank CSV exports with preamble detection, multi-format date parsing, explicit column-mapping correction for ambiguous files, and deterministic SHA-256 duplicate prevention across uploads.
- **Deterministic Python Financial Engine:** Computes total income, net expenses, refunds/reversals, internal transfer exclusions, net cash flow, running/opening balance, savings rate, month-over-month changes, top spending merchants, and recurring expense detection using `decimal.Decimal` (never LLM-generated arithmetic).
- **Hybrid AI Transaction Categorisation:** Applies fast deterministic rules first, batches only PII-scrubbed low-confidence merchants to `gemini-3.5-flash-lite` using structured JSON outputs, validates categories against a strict allowlist, and preserves user-corrected categories unconditionally.
- **Interactive Monthly Budgets:** Create and edit category limits per month with live spent vs. remaining tracking and colour-coded utilisation alerts (`on_track`, `warning`, `exceeded`).
- **Context-Aware AI Copilot:** Natural-language financial Q&A powered by `gemini-4-hydrogen`, grounded strictly in verified backend Python metrics for the authenticated user, with transparent fallback if the AI service is unavailable.
- **Zero-Credential Privacy & Strict Auth Isolation:** Never requests bank passwords, CVVs, or UPI PINs; verifies Firebase ID tokens on every private endpoint; scopes all Firestore reads/writes to the authenticated UID; and strictly isolates synthetic Demo Mode from authenticated accounts.

---

## Architecture

```text
[ React + Vite + Tailwind + Recharts ]
   (Firebase Hosting + Firebase Web Auth)
                 │
                 │  HTTPS + Firebase Bearer ID Token
                 ▼
[ Python 3.12 + FastAPI on Google Cloud Run ]
   ├── api/deps.py             -> Firebase ID Token verification (strict 401/503)
   ├── core/security.py        -> PII scrubbing & CSV formula injection protection
   ├── services/csv_parser.py  -> SBI / HDFC / ICICI / Generic Pandas + Decimal parser
   ├── services/categorizer.py -> Deterministic rules + gemini-3.5-flash-lite batch JSON
   ├── services/analytics.py   -> Deterministic Decimal financial calculations
   ├── services/gemini_service -> Grounded Q&A via gemini-4-hydrogen (google-genai SDK)
   └── services/firestore_svc  -> UID-scoped Cloud Firestore repository
```

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 18, Vite 6, Tailwind CSS 3, Recharts, Lucide React, Firebase JS SDK v11 |
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pydantic v2, Pandas, `decimal.Decimal` |
| **AI** | Official `google-genai` Python SDK (`gemini-4-hydrogen` for chat, `gemini-3.5-flash-lite` for batch categorisation) |
| **Auth & DB** | Firebase Authentication, Cloud Firestore (Native Mode) |
| **Testing & CI/CD** | Pytest, HTTPX, GitHub Actions, Docker (Cloud Run), Firebase Hosting |

---

## Project Directory Structure

```text
money-manager/
├── .github/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
├── .gitignore
├── .env.example
├── README.md
├── firebase.json
├── firestore.rules
├── frontend/
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       ├── data/demoData.js
│       ├── utils/formatters.js
│       ├── services/{api.js,firebase.js}
│       └── components/
│           ├── Sidebar.jsx
│           ├── SummaryCards.jsx
│           ├── SpendingChart.jsx
│           ├── BudgetProgress.jsx
│           ├── TransactionTable.jsx
│           ├── CsvUploadModal.jsx
│           └── AiAssistantPanel.jsx
└── backend/
    ├── Dockerfile
    ├── pytest.ini
    ├── requirements.txt
    ├── tests/
    │   ├── conftest.py
    │   ├── fixtures/{sample_statement.csv,sbi_sample.csv,hdfc_sample.csv,icici_sample.csv}
    │   ├── test_security.py
    │   ├── test_csv_parser.py
    │   ├── test_analytics.py
    │   └── test_routes.py
    └── app/
        ├── __init__.py
        ├── main.py
        ├── core/{__init__.py,config.py,security.py}
        ├── models/{__init__.py,schemas.py}
        ├── services/{__init__.py,csv_parser.py,categorizer.py,analytics.py,gemini_service.py,firestore_service.py}
        └── api/
            ├── __init__.py
            ├── deps.py
            └── routes/{__init__.py,health.py,upload.py,transactions.py,budgets.py,analytics.py,chat.py}
```

---

## Prerequisites

- **Python 3.11 or 3.12** (`python --version`)
- **Node.js 20 LTS & npm** (`node --version`, `npm --version`)
- **Git**
- A **Firebase project** with Authentication (Google Sign-In enabled) and Cloud Firestore enabled
- A **Google AI Studio API Key** (`GEMINI_API_KEY`)

---

## Windows PowerShell Setup Instructions

### 1. Extract & Open Project Directory
```powershell
Expand-Archive -Path .\money-manager.zip -DestinationPath .
cd .\money-manager
```

### 2. Configure Environment Variables
```powershell
Copy-Item .env.example .env
Copy-Item frontend\.env.example frontend\.env
```

Edit `.env` (backend) and populate:
- `GEMINI_API_KEY` — Your Google AI Studio API key (server-side only).
- `FIREBASE_PROJECT_ID` — Your Firebase project ID.
- `GOOGLE_APPLICATION_CREDENTIALS` — Path to your downloaded Firebase Admin service account JSON file (e.g., `./serviceAccountKey.json`). Never commit this file.
- `ALLOWED_ORIGINS` — `http://localhost:5173,http://127.0.0.1:5173`

Edit `frontend/.env` and populate your Firebase Web App keys (`VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_STORAGE_BUCKET`, `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`). Never place `GEMINI_API_KEY` in `frontend/.env`.

### 3. Firebase Configuration
1. Open the [Firebase Console](https://console.firebase.google.com/) and create/select your project.
2. Navigate to **Authentication -> Sign-in method** and enable **Google**.
3. Navigate to **Firestore Database -> Create database** (Native Mode).
4. Deploy `firestore.rules` using the Firebase CLI:
   ```powershell
   npm install -g firebase-tools
   firebase login
   firebase deploy --only firestore:rules
   ```
5. Download a Service Account JSON key from **Project Settings -> Service accounts -> Generate new private key**, save it as `serviceAccountKey.json` in the project root (already ignored in `.gitignore`), and set `GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json` in `.env`.

### 4. Gemini API Configuration
1. Visit [Google AI Studio](https://aistudio.google.com/apikey) and generate an API key.
2. Add `GEMINI_API_KEY=your_key_here` to `.env`.
3. Verified official model IDs configured in `.env.example`:
   - `GEMINI_CHAT_MODEL=gemini-4-hydrogen`
   - `GEMINI_BATCH_MODEL=gemini-3.5-flash-lite`

### 5. Backend Installation (Windows PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Frontend Installation (Windows PowerShell)
Open a second PowerShell window in `money-manager`:
```powershell
cd frontend
npm install
```

---

## Running Locally

**Terminal 1 — Start FastAPI Backend:**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- Verify health check: `http://127.0.0.1:8000/api/health`
- Interactive OpenAPI docs: `http://127.0.0.1:8000/docs`

**Terminal 2 — Start React Frontend:**
```powershell
cd frontend
npm run dev
```
- Open `http://localhost:5173`.
- Before signing in, the UI opens in clearly labelled **Synthetic Demo Mode**.
- Click **Sign In with Google** to switch to your private Firestore-backed workspace and upload CSV statements.

---

## Running Automated Tests

**Backend Pytest Suite:**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pytest -v
```

**Frontend Production Build Verification:**
```powershell
cd frontend
npm run build
```

---

## GitHub Branch Workflow

- `main` — Production release branch. Protected; merges only from `develop` or `hotfix/*` after CI passes. Automatically deploys to Cloud Run and Firebase Hosting via `.github/workflows/deploy.yml`.
- `develop` — Integration branch for verified PRs.
- Feature / security / QA branches follow `<type>/<layer>-<scope>` naming:
  - `sec/auth-and-pii-hardening`
  - `feat/be-csv-and-analytics`
  - `feat/be-firestore-persistence`
  - `feat/ai-gemini-categorizer-and-tools`
  - `feat/fe-auth-and-state-sync`
  - `feat/fe-budgets-and-tx-editor`
  - `test/be-unit-and-integration`
  - `chore/ci-cd-gcp-deploy`

---

## Deployment Instructions (Cloud Run & Firebase Hosting)

Configure the following GitHub Repository Secrets before pushing to `main`:
- `GCP_SA_KEY`, `GCP_REGION`, `CLOUD_RUN_SERVICE_NAME`
- `FIREBASE_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT`, `FRONTEND_ORIGIN`
- `VITE_API_BASE_URL`, `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_STORAGE_BUCKET`, `VITE_FIREBASE_MESSAGING_SENDER_ID`, `VITE_FIREBASE_APP_ID`
- Store `GEMINI_API_KEY` in **Google Cloud Secret Manager** (referenced by Cloud Run via `--set-secrets=GEMINI_API_KEY=GEMINI_API_KEY:latest`).

---

## Security Considerations

- **Independent Backend Authorization:** Because the Firebase Admin SDK bypasses Firestore Security Rules, every method in `FirestoreRepository` independently scopes paths under `users/{uid}/...` and verifies stored `uid == authenticated_user.uid`.
- **Zero Shared Guest Identity:** Authenticated endpoints strictly require a valid Firebase Bearer token and reject missing, invalid, revoked, or expired tokens with `HTTP 401`.
- **PII Redaction & Formula Safety:** `core/security.py` scrubs UPI VPAs, emails, phone numbers, card numbers, IFSC/PAN codes, and long numeric references before storage or Gemini calls, and neutralizes CSV formula injection prefixes (`=`, `+`, `@`).
- **Explicit CORS:** `ALLOWED_ORIGINS` rejects wildcard `*` when credentials are enabled.

---

## Known Limitations

- Bank CSV parsers are explicitly implemented and tested for **SBI**, **HDFC**, **ICICI**, and **Generic** CSV exports. Password-protected PDF bank statements are not supported natively (export as CSV and use the built-in Column Mapping UI for non-standard headers).
- Firestore queries currently filter transactions in Python after streaming the authenticated user's UID collection to avoid requiring composite Firestore indexes during initial setup; for accounts exceeding ~5,000 transactions, add composite Firestore indexes on `(date, category)`.
- Currency display defaults to INR (`₹`) in `frontend/src/utils/formatters.js`.
