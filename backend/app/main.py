import json
import os
from pathlib import Path
from statistics import mean
from typing import Any, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


class InterviewRequest(BaseModel):
    sessionId: str = Field(min_length=1)
    candidate: Optional[dict[str, Any]] = None
    message: Optional[str] = None

    @model_validator(mode="after")
    def requires_candidate_or_message(self):
        if self.candidate is None and not self.message:
            raise ValueError("Provide candidate to start or message for a conversation turn.")
        return self


class Feedback(BaseModel):
    summary: str
    strengths: list[str]
    gaps: list[str]
    next: list[str]


class InterviewResponse(BaseModel):
    reply: str
    done: bool
    feedback: Optional[Feedback] = None


app = FastAPI(title="SkillProbe AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)
sessions: dict[str, dict[str, Any]] = {}


def load_json(name: str) -> dict[str, Any]:
    with (DATA_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


CURRICULUM = load_json("curriculum.json")


def gemini_reply(instruction: str) -> Optional[str]:
    """Use Gemini when configured, while preserving a complete offline demo."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model="gemini-2.0-flash", contents=instruction)
        return response.text.strip() if response.text else None
    except Exception:
        return None


def profile(candidate: dict[str, Any]) -> dict[str, Any]:
    """Accept exactly the organizer profile object, or a candidates[] wrapper for convenience."""
    if "member" in candidate:
        return candidate
    if "candidates" in candidate and candidate["candidates"]:
        return candidate["candidates"][0]
    raise HTTPException(status_code=422, detail="candidate must use the supplied candidate profile schema")


def day_index() -> dict[int, dict[str, Any]]:
    return {item["day"]: item for item in CURRICULUM["days"]}


def weak_and_strong_topics(candidate: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    days = day_index()
    missions = candidate.get("missions", [])
    weak = [m for m in missions if m.get("skipped") or m.get("passed") is False or m.get("attempts", 1) >= 4]
    strong = [m for m in missions if m.get("passed") is True and m.get("attempts", 1) == 1]
    weak_days = [days[m["day"]] for m in weak if m.get("day") in days]
    strong_days = [days[m["day"]] for m in strong if m.get("day") in days]
    fallback = [days[number] for number in (7, 10, 13, 20, 22, 27, 31) if number in days]
    return (weak_days or fallback, strong_days or fallback)


def question_for(topic: dict[str, Any], member: dict[str, Any], index: int) -> str:
    objective = topic["objectives"][index % len(topic["objectives"])]
    role = member.get("jobRole", "your role")
    return (
        f"Question {index + 1}/8 — {topic['title']} (Day {topic['day']}): "
        f"As a {role}, how would you {objective.lower()}? Explain your approach, trade-offs, and how you would validate it."
    )


def plan(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    weak, strong = weak_and_strong_topics(candidate)
    pool = weak + strong
    selected: list[dict[str, Any]] = []
    seen: set[int] = set()
    for topic in pool:
        if topic["day"] not in seen:
            selected.append(topic)
            seen.add(topic["day"])
        if len(selected) == 8:
            break
    days = day_index()
    for topic in days.values():
        if len(selected) == 8:
            break
        if topic["day"] not in seen:
            selected.append(topic)
            seen.add(topic["day"])
    return selected


def answer_score(message: str) -> int:
    words = message.split()
    evidence = sum(token in message.lower() for token in ("because", "trade-off", "measure", "test", "monitor", "validate", "example"))
    return min(5, max(1, (len(words) >= 35) + (len(words) >= 80) + evidence + 1))


def follow_up(topic: dict[str, Any], answer: str) -> str:
    generated = gemini_reply(
        "You are a concise technical interviewer. Write one follow-up question, under 45 words, "
        f"about this curriculum topic: {topic['title']}. Candidate answer: {answer}"
    )
    if generated:
        return generated
    if answer_score(answer) <= 2:
        return f"Follow-up on Day {topic['day']}: please make that concrete—what would you build first, and what signal would tell you it worked?"
    return f"Follow-up on Day {topic['day']}: good direction. What trade-off would you make under tighter latency, cost, or reliability constraints?"


def final_feedback(session: dict[str, Any]) -> Feedback:
    member = session["candidate"]["member"]
    scores = session["scores"] or [3]
    weak, strong = weak_and_strong_topics(session["candidate"])
    strengths = [f"Clear engagement with {topic['title']}." for topic in strong[:2]]
    strengths.append("Communicated a solution approach across a sustained technical conversation.")
    gaps = [f"Deepen hands-on confidence in {topic['title']}." for topic in weak[:2]]
    if mean(scores) < 3:
        gaps.append("Use more concrete implementation details and validation metrics in technical explanations.")
    next_steps = [
        f"Build a small artifact applying {topic['title']} and document the design trade-offs." for topic in weak[:2]
    ]
    next_steps.append("Practice concise STAR-style answers that include architecture, measurement, and failure handling.")
    return Feedback(
        summary=(f"{member.get('name', 'The candidate')} completed an adaptive eight-question interview spanning "
                 f"{len({q['day'] for q in session['plan']})} curriculum topics. Average response depth: {mean(scores):.1f}/5."),
        strengths=strengths[:3], gaps=gaps[:3], next=next_steps[:3],
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "gemini" if os.getenv("GEMINI_API_KEY") else "demo"}


@app.post("/api/interview", response_model=InterviewResponse)
def interview(request: InterviewRequest) -> InterviewResponse:
    if request.candidate is not None:
        candidate = profile(request.candidate)
        interview_plan = plan(candidate)
        sessions[request.sessionId] = {
            "candidate": candidate, "plan": interview_plan, "question_index": 0,
            "awaiting_followup": False, "scores": [], "history": [],
        }
        member = candidate["member"]
        reply = (f"Welcome, {member.get('name', 'candidate')}. I tailored this interview to your {member.get('jobRole', 'background')} "
                 f"and curriculum history. We’ll cover at least four topics in eight questions. {question_for(interview_plan[0], member, 0)}")
        return InterviewResponse(reply=reply, done=False)

    session = sessions.get(request.sessionId)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown sessionId. Start with a candidate profile.")
    message = request.message or ""
    session["history"].append({"role": "candidate", "content": message})
    session["scores"].append(answer_score(message))
    current = session["plan"][session["question_index"]]
    if not session["awaiting_followup"] and answer_score(message) <= 3:
        session["awaiting_followup"] = True
        return InterviewResponse(reply=follow_up(current, message), done=False)
    session["awaiting_followup"] = False
    session["question_index"] += 1
    if session["question_index"] >= 8:
        return InterviewResponse(reply="Interview completed.", done=True, feedback=final_feedback(session))
    index = session["question_index"]
    return InterviewResponse(reply=question_for(session["plan"][index], session["candidate"]["member"], index), done=False)
