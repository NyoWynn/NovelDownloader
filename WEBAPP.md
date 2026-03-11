# NovelDownloader Web Migration

Este workspace ahora tiene una arquitectura web separada:

- `frontend/`: Next.js para desplegar en Vercel
- `backend/`: FastAPI para desplegar en Railway

## Desarrollo local

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Disponible en `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Disponible en `http://localhost:3000`.

Crea `frontend/.env.local` con:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Deploy

### Railway

- Root directory: `backend`
- Install command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Vercel

- Root directory: `frontend`
- Framework preset: Next.js
- Env var: `NEXT_PUBLIC_API_BASE_URL=https://tu-backend.up.railway.app`

## Limitaciones actuales

- Los jobs viven en memoria; si Railway reinicia, se pierde el estado.
- Los PDFs se guardan temporalmente en el filesystem del contenedor.
- Para escalar, conviene luego mover jobs a Redis/DB y archivos a S3 o similar.
