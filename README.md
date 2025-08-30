# 🚀 Synapse - Backend

## ⚙️ How to Run the Project

Follow these steps to set up and run the application in your local environment.

## 📦 1. Clone the project
```bash
git clone https://github.com/Grupo-Syntax-Squad/synapse-backend.git
cd synapse-backend
```

## 🐍 2. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate     # Windows
```

## 📥 3. Install dependencies
```bash
pip install -r requirements.txt
```

## ⚙️ 4. Database configuration
Create a `.env` file in the root directory:

```
DATABASE_URL=postgresql://postgres:password@localhost:5432/synapse
```

## ▶️ 5. Run the application
```bash
uvicorn app.main:app --reload
```

By default, the API will be available at:  
👉 [http://localhost:8000](http://localhost:8000)

---

## 🧹 6. Code quality

### Check types with **Mypy**
```bash
mypy app/
```

### Lint and formatting with **Ruff**
```bash
ruff check .
ruff format .
```