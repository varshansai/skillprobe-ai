# SkillProbe AI

Adaptive Technical Interview Agent built for the provided curriculum and candidate profiles.

## Run

1. Backend: `cd backend`, then install `pip install -r requirements.txt`, then run `uvicorn app.main:app --reload --port 8000`.
2. Frontend: `cd frontend`, run `npm install`, then `npm run dev`.
3. Open `http://localhost:3000`.

The required API is `POST /api/interview`. It uses in-memory sessions and runs in a reliable deterministic demo mode when `GEMINI_API_KEY` is absent.

## Contract

Start with `{ "sessionId": "abc-123", "candidate": { ... } }`, then send `{ "sessionId": "abc-123", "message": "..." }` for each answer. The eighth question completes with the required structured feedback.
