"use client";
import { FormEvent, useState } from "react";
import candidatesData from "../../data/candidates.json";

type Chat = { role: "agent" | "candidate"; content: string };
type Feedback = { summary: string; strengths: string[]; gaps: string[]; next: string[] };
const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [candidateIndex, setCandidateIndex] = useState(0);
  const [sessionId, setSessionId] = useState("");
  const [chat, setChat] = useState<Chat[]>([]);
  const [message, setMessage] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [loading, setLoading] = useState(false);
  const candidates = candidatesData.candidates;
  const candidate = candidates[candidateIndex];
  async function call(payload: object) {
    const response = await fetch(`${api}/api/interview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error((await response.json()).detail || "Could not reach the interview service.");
    return response.json();
  }
  async function start() {
    setLoading(true); setFeedback(null); const id = crypto.randomUUID();
    try { const result = await call({ sessionId: id, candidate }); setSessionId(id); setChat([{ role: "agent", content: result.reply }]); }
    catch (error) { setChat([{ role: "agent", content: error instanceof Error ? error.message : "Unable to start." }]); }
    finally { setLoading(false); }
  }
  async function send(event: FormEvent) {
    event.preventDefault(); if (!message.trim() || !sessionId || loading || feedback) return;
    const text = message.trim(); setMessage(""); setChat((items) => [...items, { role: "candidate", content: text }]); setLoading(true);
    try { const result = await call({ sessionId, message: text }); setChat((items) => [...items, { role: "agent", content: result.reply }]); if (result.done) setFeedback(result.feedback); }
    catch (error) { setChat((items) => [...items, { role: "agent", content: error instanceof Error ? error.message : "Unable to continue." }]); }
    finally { setLoading(false); }
  }
  return <main className="min-h-screen bg-slate-950 text-slate-100"><div className="mx-auto max-w-6xl px-5 py-10"><header className="mb-10 flex flex-col gap-3 md:flex-row md:items-end md:justify-between"><div><p className="text-sm font-semibold uppercase tracking-[.25em] text-cyan-400">Adaptive technical interview agent</p><h1 className="mt-2 text-4xl font-black tracking-tight">SkillProbe <span className="text-cyan-400">AI</span></h1><p className="mt-2 max-w-xl text-slate-400">Personalized, curriculum-aware technical interviews with live adaptive follow-ups.</p></div><div className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">● Demo mode ready</div></header><div className="grid gap-6 lg:grid-cols-[320px_1fr]"><aside className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5"><h2 className="font-bold">Candidate profile</h2><select value={candidateIndex} onChange={(e) => setCandidateIndex(Number(e.target.value))} className="mt-4 w-full rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm">{candidates.map((item, index) => <option key={item.member.id} value={index}>{item.member.name} — {item.member.jobRole}</option>)}</select><div className="mt-5 space-y-3 text-sm"><Info label="Experience" value={`${candidate.member.yearsExperience} years`} /><Info label="Education" value={candidate.member.education} /><Info label="Completed" value={`${candidate.signals.missionsCompleted}/31 missions`} /><Info label="Commitment" value={`${candidate.signals.commitDays} days`} /></div><button onClick={start} disabled={loading} className="mt-6 w-full rounded-lg bg-cyan-400 px-4 py-3 font-bold text-slate-950 transition hover:bg-cyan-300 disabled:opacity-50">{loading ? "Starting…" : "Start tailored interview"}</button><p className="mt-3 text-xs leading-relaxed text-slate-500">Eight questions · four+ curriculum topics · adaptive depth probes</p></aside><section className="flex min-h-[590px] flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/70"><div className="border-b border-slate-800 px-6 py-4"><h2 className="font-bold">Interview room</h2><p className="text-xs text-slate-500">Conversation context stays in this session.</p></div><div className="flex-1 space-y-4 overflow-y-auto p-6">{chat.length === 0 ? <div className="grid h-full place-items-center text-center text-slate-500"><div><p className="text-lg text-slate-300">Ready when you are.</p><p className="mt-2">Choose a profile and start the interview.</p></div></div> : chat.map((item, i) => <div key={i} className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm leading-6 ${item.role === "agent" ? "bg-slate-800 text-slate-100" : "ml-auto bg-cyan-400 text-slate-950"}`}>{item.content}</div>)}{loading && <div className="w-fit rounded-2xl bg-slate-800 px-4 py-3 text-sm text-slate-400">SkillProbe is thinking…</div>}{feedback && <FeedbackCard feedback={feedback} />}</div><form onSubmit={send} className="flex gap-3 border-t border-slate-800 p-4"><input value={message} onChange={(e) => setMessage(e.target.value)} disabled={!sessionId || !!feedback || loading} placeholder={sessionId ? "Share your answer…" : "Start an interview first"} className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm outline-none placeholder:text-slate-600 focus:border-cyan-400"/><button disabled={!sessionId || !!feedback || loading} className="rounded-lg bg-slate-100 px-5 py-3 text-sm font-bold text-slate-950 disabled:opacity-40">Send</button></form></section></div></div></main>;
}
function Info({ label, value }: { label: string; value: string }) { return <div><p className="text-slate-500">{label}</p><p className="mt-0.5 text-slate-200">{value}</p></div>; }
function FeedbackCard({ feedback }: { feedback: Feedback }) { return <div className="rounded-2xl border border-cyan-400/30 bg-cyan-400/10 p-5 text-sm"><h3 className="font-bold text-cyan-300">Final feedback</h3><p className="mt-2 text-slate-200">{feedback.summary}</p><div className="mt-4 grid gap-4 md:grid-cols-3">{([['Strengths', feedback.strengths], ['Growth areas', feedback.gaps], ['Next steps', feedback.next]] as const).map(([title, items]) => <div key={title}><p className="font-semibold text-slate-100">{title}</p><ul className="mt-2 space-y-1 text-slate-300">{items.map((item) => <li key={item}>• {item}</li>)}</ul></div>)}</div></div>; }
