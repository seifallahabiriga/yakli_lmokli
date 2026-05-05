# University Observatory: Multi-Agent System for Opportunities

Yakli Lmokli is a comprehensive **Multi-Agent System** designed for the management, discovery, and recommendation of **Internships, Projects, Certifications, and Scholarships**. 

The platform leverages a modern stack, combining a high-performance **FastAPI** backend with a dynamic **React (Vite + TanStack)** frontend. It integrates various AI/ML techniques, including local embedding models, cloud-based LLMs, and multi-agent frameworks, to scrape, process, and recommend opportunities effectively.

---

## 🚀 Features

- **Multi-Agent Architecture**: Uses `Mesa` to run specialized agents for scraping, filtering, and curating opportunities.
- **Automated Scraping Engine**: Built with `Playwright`, `BeautifulSoup`, and `feedparser` to continuously discover new opportunities from various sources.
- **Intelligent Recommendations**: Combines `sentence-transformers`, `faiss`, and `scikit-learn` for semantic search, clustering, and personalized matching.
- **Asynchronous Task Queue**: Uses `Celery` and `Redis` to manage heavy background tasks, such as model training, data scraping, and email notifications.
- **Modern User Interface**: A fast, responsive frontend built with `React`, `TanStack Router`, `Tailwind CSS`, and `Radix UI` components.

---

## 🛠️ Technology Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11+)
- **Database**: PostgreSQL (via `asyncpg` and `SQLAlchemy`) + Alembic for migrations
- **Task Queue**: Celery + Redis (with Flower for monitoring)
- **Machine Learning**: PyTorch, sentence-transformers, FAISS, scikit-learn, spaCy
- **LLM Integration**: Google Generative AI (Gemini), Groq
- **Multi-Agent**: Mesa
- **Monitoring**: Prometheus client, Loguru

### Frontend
- **Framework**: React 19 + [Vite](https://vitejs.dev/)
- **Routing & State**: TanStack Router, TanStack Start, TanStack Query
- **Styling**: Tailwind CSS v4, Radix UI Primitives, Lucide React (Icons)
- **Forms & Validation**: React Hook Form + Zod

---

## 📂 Project Structure

```text
aya_bikomchi/
├── backend/            # FastAPI application, background workers, and ML models
│   ├── api/            # API routes (auth, user, opportunity, etc.)
│   ├── core/           # Configuration and exceptions
│   ├── db/             # SQLAlchemy models and session management
│   ├── job_queue/      # Celery producer and Redis configuration
│   ├── middleware/     # Rate limiting, logging, etc.
│   ├── monitoring/     # Health checks and Prometheus metrics
│   └── main.py         # FastAPI application entry point
├── frontend/           # Vite + React application
│   ├── src/            # Components, routes, and UI assets
│   ├── package.json    # Frontend dependencies
│   └── vite.config.ts  # Vite configuration
├── alembic/            # Database migration scripts
├── data/               # Local data storage for embeddings/models
├── requirements.txt    # Python dependencies
└── full_test.ps1       # Script for system testing
```

---

## ⚙️ Getting Started

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL
- Redis
- Playwright dependencies (Chromium)

### 1. Backend Setup

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install ML resources and browser binaries:**
   ```bash
   python -m spacy download en_core_web_sm
   playwright install chromium
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory based on `.env.example` (if provided) and configure your database, Redis URL, and API keys.

5. **Run Database Migrations:**
   ```bash
   alembic upgrade head
   ```

6. **Start the FastAPI Server:**
   ```bash
   uvicorn backend.main:app --reload
   ```

7. **Start Celery Worker (in a separate terminal):**
   ```bash
   # Make sure your virtual environment is activated
   celery -A backend.job_queue.worker worker --loglevel=info
   ```

### 2. Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```
   The frontend will typically be accessible at `http://localhost:5173`.

---

## 📊 Monitoring and Admin

- **FastAPI Docs (Swagger UI):** `http://localhost:8000/docs`
- **Celery Flower (Task Dashboard):** `http://localhost:5555` (if running Flower)
- **Health Check Endpoint:** `http://localhost:8000/health`

## 📝 License
This project is proprietary. All rights reserved.