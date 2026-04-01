import { useState, useRef, useEffect, useCallback } from "react";

// ─── Mock data (replace with real API calls) ────────────────────────────────
const MOCK_PROJECT = {
  id: "proj-001",
  title: "oppm ai work management system",
  leader: "cheongchoonvai",
  start_date: "Apr 1, 2026",
  deadline: "Jun 1, 2026",
  status: "Planning",
  progress: 0,
  deliverable: "",
};

const WEEKS = [
  { label: "W1", date: "MAR 30" },
  { label: "W2", date: "APR 6" },
  { label: "W3", date: "APR 13" },
  { label: "W4", date: "APR 20" },
  { label: "W5", date: "APR 27" },
  { label: "W6", date: "MAY 4" },
  { label: "W7", date: "MAY 11" },
  { label: "W8", date: "MAY 18" },
];

const INITIAL_OBJECTIVES = [
  { id: "obj-1", title: "Database & backend setup", owner: "cheongchoonvai", timeline: { W1: "in_progress", W2: "in_progress" } },
  { id: "obj-2", title: "Authentication & workspaces", owner: "cheongchoonvai", timeline: { W2: "planned", W3: "planned" } },
  { id: "obj-3", title: "OPPM grid UI", owner: "", timeline: { W3: "planned", W4: "planned" } },
  { id: "obj-4", title: "AI chat integration", owner: "", timeline: { W4: "planned", W5: "planned" } },
  { id: "obj-5", title: "GitHub webhook & analysis", owner: "", timeline: { W5: "planned", W6: "planned" } },
];

const TEAM = [
  { slot: "Project Leader", name: "cheongchoonvai" },
  { slot: "Member 1", name: "" },
  { slot: "Member 2", name: "" },
  { slot: "Member 3", name: "" },
  { slot: "Member 4", name: "" },
];

const STATUS_CONFIG = {
  planned:     { color: "#9CA3AF", label: "Planned" },
  in_progress: { color: "#3B82F6", label: "In Progress" },
  completed:   { color: "#22C55E", label: "Completed" },
  at_risk:     { color: "#F59E0B", label: "At Risk" },
  blocked:     { color: "#EF4444", label: "Blocked" },
  empty:       { color: "transparent", label: "None" },
};

const STATUS_CYCLE = ["empty", "planned", "in_progress", "completed", "at_risk", "blocked"];

// ─── Helpers ─────────────────────────────────────────────────────────────────
function nextStatus(current) {
  const idx = STATUS_CYCLE.indexOf(current || "empty");
  return STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
}

function calcProgress(objectives) {
  let total = 0, filled = 0;
  objectives.forEach(obj => {
    WEEKS.forEach(w => {
      total++;
      const s = obj.timeline[w.label];
      if (s && s !== "empty") filled++;
    });
  });
  return Math.round((filled / total) * 100);
}

// ─── AI Chat using Anthropic API ─────────────────────────────────────────────
async function sendToAI(messages, projectContext) {
  const systemPrompt = `You are OPPM AI, a project management assistant specialized in the One Page Project Manager (OPPM) methodology.

Current project context:
${projectContext}

You help users manage their OPPM by:
- Suggesting objectives and timeline status updates
- Analyzing project health and identifying risks
- Creating structured plans from natural language descriptions

When the user wants to make changes, respond with a JSON action block at the END of your message in this exact format:
<action>
{
  "type": "set_timeline" | "add_objective" | "update_objective" | "none",
  "data": { ... }
}
</action>

For set_timeline: data = { "objective_id": "...", "week": "W1", "status": "completed|in_progress|at_risk|blocked|planned" }
For add_objective: data = { "title": "...", "owner": "..." }
For update_objective: data = { "objective_id": "...", "title": "..." }
For none: just respond conversationally.

Keep responses concise and action-oriented. Max 3 sentences unless explaining a plan.`;

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 1000,
      system: systemPrompt,
      messages: messages.map(m => ({ role: m.role, content: m.content })),
    }),
  });

  const data = await response.json();
  const text = data.content?.[0]?.text || "Sorry, I couldn't process that.";

  // Parse action block if present
  const actionMatch = text.match(/<action>([\s\S]*?)<\/action>/);
  let action = null;
  if (actionMatch) {
    try { action = JSON.parse(actionMatch[1].trim()); } catch {}
  }
  const cleanText = text.replace(/<action>[\s\S]*?<\/action>/g, "").trim();

  return { text: cleanText, action };
}

// ─── Components ──────────────────────────────────────────────────────────────
function StatusDot({ status, onClick, small }) {
  const cfg = STATUS_CONFIG[status || "empty"];
  const size = small ? 10 : 14;
  return (
    <div
      onClick={onClick}
      title={cfg.label}
      style={{
        width: size, height: size,
        borderRadius: "50%",
        background: status && status !== "empty" ? cfg.color : "transparent",
        border: `1.5px solid ${status && status !== "empty" ? cfg.color : "#D1D5DB"}`,
        cursor: onClick ? "pointer" : "default",
        transition: "all 0.15s",
        flexShrink: 0,
      }}
    />
  );
}

function InlineEdit({ value, placeholder, onSave, style = {} }) {
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState(value);
  const ref = useRef();

  useEffect(() => { if (editing) ref.current?.focus(); }, [editing]);
  useEffect(() => { setVal(value); }, [value]);

  if (!editing) return (
    <span
      onClick={() => setEditing(true)}
      style={{
        cursor: "text", borderRadius: 4, padding: "1px 3px",
        color: val ? "inherit" : "#9CA3AF",
        ...style,
      }}
      title="Click to edit"
    >
      {val || placeholder}
    </span>
  );

  return (
    <input
      ref={ref}
      value={val}
      onChange={e => setVal(e.target.value)}
      onBlur={() => { onSave(val); setEditing(false); }}
      onKeyDown={e => { if (e.key === "Enter") { onSave(val); setEditing(false); } if (e.key === "Escape") { setVal(value); setEditing(false); } }}
      style={{
        background: "transparent", border: "none",
        borderBottom: "1.5px solid #3B82F6",
        outline: "none", width: "100%",
        fontSize: "inherit", color: "inherit",
        padding: "1px 3px", ...style,
      }}
    />
  );
}

function ChatMessage({ msg }) {
  const isUser = msg.role === "user";
  return (
    <div style={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start", marginBottom: 10 }}>
      <div style={{
        maxWidth: "82%", padding: "8px 12px",
        background: isUser ? "#3B82F6" : "#F3F4F6",
        color: isUser ? "#fff" : "#111827",
        borderRadius: isUser ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
        fontSize: 13, lineHeight: 1.5,
      }}>
        {msg.content}
        {msg.action && msg.action.type !== "none" && (
          <div style={{ marginTop: 6, padding: "4px 8px", background: "rgba(255,255,255,0.2)", borderRadius: 6, fontSize: 11, opacity: 0.85 }}>
            ✓ Action applied: {msg.action.type.replace("_", " ")}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function OPPMEditor() {
  const [project, setProject] = useState(MOCK_PROJECT);
  const [objectives, setObjectives] = useState(INITIAL_OBJECTIVES);
  const [team, setTeam] = useState(TEAM);
  const [deliverables, setDeliverables] = useState(["", "", "", ""]);
  const [forecast, setForecast] = useState(["", "", "", ""]);
  const [risks, setRisks] = useState(["", "", "", ""]);
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! I'm your OPPM assistant. I can help you set up objectives, update timeline status, or analyze your project. What would you like to do?" }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef();
  const inputRef = useRef();

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const progress = calcProgress(objectives);

  const toggleDot = useCallback((objId, week) => {
    setObjectives(prev => prev.map(obj => {
      if (obj.id !== objId) return obj;
      const current = obj.timeline[week] || "empty";
      const next = nextStatus(current);
      return { ...obj, timeline: { ...obj.timeline, [week]: next === "empty" ? undefined : next } };
    }));
  }, []);

  const buildContext = () => {
    return `Project: "${project.title}"
Leader: ${project.leader} | Start: ${project.start_date} | Deadline: ${project.deadline}
Status: ${project.status} | Progress: ${progress}%

Objectives and timeline:
${objectives.map(o => `- [${o.id}] "${o.title}" (owner: ${o.owner || "unassigned"})
  Timeline: ${WEEKS.map(w => `${w.label}:${o.timeline[w.label] || "empty"}`).join(", ")}`).join("\n")}

Team: ${team.map(t => `${t.slot}: ${t.name || "empty"}`).join(", ")}`;
  };

  const applyAction = useCallback((action) => {
    if (!action || action.type === "none") return;

    if (action.type === "set_timeline" && action.data) {
      const { objective_id, week, status } = action.data;
      setObjectives(prev => prev.map(obj => {
        if (obj.id !== objective_id) return obj;
        return { ...obj, timeline: { ...obj.timeline, [week]: status } };
      }));
    }

    if (action.type === "add_objective" && action.data) {
      const newObj = {
        id: `obj-${Date.now()}`,
        title: action.data.title || "New objective",
        owner: action.data.owner || "",
        timeline: {},
      };
      setObjectives(prev => [...prev, newObj]);
    }

    if (action.type === "update_objective" && action.data) {
      const { objective_id, title } = action.data;
      setObjectives(prev => prev.map(obj =>
        obj.id === objective_id ? { ...obj, title: title || obj.title } : obj
      ));
    }
  }, []);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { role: "user", content: input.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setLoading(true);

    try {
      const { text, action } = await sendToAI(newMessages, buildContext());
      const assistantMsg = { role: "assistant", content: text, action };
      setMessages(prev => [...prev, assistantMsg]);
      if (action) applyAction(action);
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: "Something went wrong. Please try again." }]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const addObjective = () => {
    setObjectives(prev => [...prev, {
      id: `obj-${Date.now()}`,
      title: "New objective",
      owner: "",
      timeline: {},
    }]);
  };

  return (
    <div style={{ fontFamily: "'Inter', sans-serif", background: "#F9FAFB", minHeight: "100vh", padding: 0 }}>

      {/* Header */}
      <div style={{ background: "#fff", borderBottom: "1px solid #E5E7EB", padding: "10px 20px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button style={{ background: "none", border: "none", cursor: "pointer", color: "#6B7280", fontSize: 18, padding: 0 }}>←</button>
          <div>
            <div style={{ fontSize: 17, fontWeight: 600, color: "#111827" }}>OPPM — {project.title}</div>
            <div style={{ fontSize: 12, color: "#6B7280" }}>One Page Project Manager · Gantt + Matrix View</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, color: "#6B7280" }}>W1 – W8</span>
          <button
            onClick={() => setChatOpen(o => !o)}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              background: chatOpen ? "#3B82F6" : "#EFF6FF",
              color: chatOpen ? "#fff" : "#3B82F6",
              border: "none", borderRadius: 8,
              padding: "7px 14px", fontSize: 13, fontWeight: 500, cursor: "pointer",
              transition: "all 0.2s",
            }}
          >
            <span style={{ fontSize: 14 }}>✦</span>
            AI Assistant
          </button>
        </div>
      </div>

      <div style={{ display: "flex", height: "calc(100vh - 57px)" }}>

        {/* OPPM Grid */}
        <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
          <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 12, overflow: "hidden" }}>

            {/* Project Header */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 80px 1fr 80px", borderBottom: "1px solid #E5E7EB" }}>
              <div style={{ padding: "14px 16px", borderRight: "1px solid #E5E7EB" }}>
                <div style={{ fontSize: 11, color: "#9CA3AF", fontWeight: 500, marginBottom: 4 }}>PROJECT LEADER</div>
                <InlineEdit value={project.leader} placeholder="Add leader" onSave={v => setProject(p => ({ ...p, leader: v }))} style={{ fontSize: 15, fontWeight: 600, color: "#111827" }} />
              </div>
              <div style={{ padding: "14px 10px", borderRight: "1px solid #E5E7EB", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                <div style={{ fontSize: 10, color: "#6B7280", fontWeight: 600, letterSpacing: "0.05em" }}>OPPM</div>
                <div style={{ width: 32, height: 32, borderRadius: "50%", border: "2px solid #3B82F6", display: "flex", alignItems: "center", justifyContent: "center", marginTop: 4 }}>
                  <span style={{ fontSize: 10, color: "#3B82F6" }}>⊙</span>
                </div>
              </div>
              <div style={{ padding: "14px 16px", borderRight: "1px solid #E5E7EB" }}>
                <div style={{ fontSize: 11, color: "#9CA3AF", fontWeight: 500, marginBottom: 4 }}>PROJECT NAME</div>
                <InlineEdit value={project.title} placeholder="Project name" onSave={v => setProject(p => ({ ...p, title: v }))} style={{ fontSize: 15, fontWeight: 600, color: "#111827" }} />
              </div>
              <div style={{ padding: "14px 10px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                <div style={{ fontSize: 10, color: "#9CA3AF" }}>Progress</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: progress > 0 ? "#3B82F6" : "#9CA3AF" }}>{progress}%</div>
              </div>
            </div>

            {/* Project info row */}
            <div style={{ padding: "10px 16px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
              <div style={{ fontSize: 13, color: "#374151" }}>
                <b>Project Objective:</b>{" "}
                <InlineEdit value={project.title} placeholder="Add objective" onSave={v => setProject(p => ({ ...p, title: v }))} />
              </div>
              <div style={{ fontSize: 13, color: "#374151" }}>
                <b>Deliverable Output:</b>{" "}
                <InlineEdit value={project.deliverable} placeholder="Click to add deliverable output..." onSave={v => setProject(p => ({ ...p, deliverable: v }))} style={{ color: "#6B7280" }} />
              </div>
            </div>

            {/* Dates + Legend */}
            <div style={{ padding: "8px 16px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <span style={{ fontSize: 12, color: "#374151" }}>Start Date: <b>{project.start_date}</b></span>
              <span style={{ fontSize: 12, color: "#374151" }}>Deadline: <b>{project.deadline}</b></span>
              <span style={{ fontSize: 12, color: "#374151" }}>Status: <b>{project.status}</b></span>
              <div style={{ marginLeft: "auto", display: "flex", gap: 12, flexWrap: "wrap" }}>
                {Object.entries(STATUS_CONFIG).filter(([k]) => k !== "empty").map(([key, cfg]) => (
                  <div key={key} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: cfg.color }} />
                    <span style={{ fontSize: 11, color: "#6B7280" }}>{cfg.label}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Timeline grid header */}
            <div style={{ display: "grid", gridTemplateColumns: "60px 1fr 50px repeat(8, 1fr) 90px", borderBottom: "1px solid #E5E7EB", background: "#F9FAFB" }}>
              <div style={{ padding: "8px 6px", textAlign: "center", fontSize: 10, fontWeight: 600, color: "#6B7280", borderRight: "1px solid #E5E7EB" }}>SUB OBJ</div>
              <div style={{ padding: "8px 12px", fontSize: 10, fontWeight: 600, color: "#6B7280", borderRight: "1px solid #E5E7EB" }}>MAJOR TASKS (DEADLINE)</div>
              <div style={{ padding: "8px 4px", textAlign: "center", fontSize: 10, fontWeight: 600, color: "#6B7280", borderRight: "1px solid #E5E7EB" }}>%</div>
              {WEEKS.map((w, i) => (
                <div key={w.label} style={{ padding: "6px 4px", textAlign: "center", borderRight: i < 7 ? "1px solid #E5E7EB" : "none", background: i === 0 ? "#EFF6FF" : "transparent" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: i === 0 ? "#3B82F6" : "#374151" }}>{w.label}</div>
                  <div style={{ fontSize: 10, color: "#9CA3AF" }}>{w.date}</div>
                </div>
              ))}
              <div style={{ padding: "8px 6px", textAlign: "center", fontSize: 10, fontWeight: 600, color: "#6B7280", borderLeft: "1px solid #E5E7EB" }}>OWNER / PRIORITY</div>
            </div>

            {/* Objective rows */}
            {objectives.map((obj, i) => (
              <div key={obj.id} style={{ display: "grid", gridTemplateColumns: "60px 1fr 50px repeat(8, 1fr) 90px", borderBottom: "1px solid #F3F4F6", background: i % 2 === 0 ? "#fff" : "#FAFAFA" }}>
                <div style={{ padding: "0 6px", textAlign: "center", borderRight: "1px solid #E5E7EB", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontSize: 11, color: "#9CA3AF", fontWeight: 600 }}>OBJ {i + 1}</span>
                </div>
                <div style={{ padding: "10px 12px", borderRight: "1px solid #E5E7EB", display: "flex", flexDirection: "column", justifyContent: "center" }}>
                  <InlineEdit
                    value={obj.title}
                    placeholder="Objective title"
                    onSave={v => setObjectives(prev => prev.map(o => o.id === obj.id ? { ...o, title: v } : o))}
                    style={{ fontSize: 13, fontWeight: 500, color: "#111827" }}
                  />
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", borderRight: "1px solid #E5E7EB" }}>
                  <span style={{ fontSize: 11, color: "#6B7280" }}>
                    {Math.round(Object.values(obj.timeline).filter(s => s === "completed").length / WEEKS.length * 100)}%
                  </span>
                </div>
                {WEEKS.map((w, wi) => (
                  <div key={w.label} style={{ display: "flex", alignItems: "center", justifyContent: "center", borderRight: wi < 7 ? "1px solid #E5E7EB" : "none", padding: 6, background: wi === 0 ? "#F5F9FF" : "transparent" }}>
                    <StatusDot
                      status={obj.timeline[w.label] || "empty"}
                      onClick={() => toggleDot(obj.id, w.label)}
                    />
                  </div>
                ))}
                <div style={{ padding: "8px 8px", borderLeft: "1px solid #E5E7EB", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <InlineEdit
                    value={obj.owner}
                    placeholder="Owner"
                    onSave={v => setObjectives(prev => prev.map(o => o.id === obj.id ? { ...o, owner: v } : o))}
                    style={{ fontSize: 11, color: "#374151", textAlign: "center" }}
                  />
                </div>
              </div>
            ))}

            {/* Add objective */}
            <div style={{ padding: "8px 12px", borderBottom: "1px solid #E5E7EB" }}>
              <button
                onClick={addObjective}
                style={{ background: "none", border: "1px dashed #D1D5DB", borderRadius: 6, padding: "6px 14px", fontSize: 12, color: "#6B7280", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}
              >
                <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> Add objective
              </button>
            </div>

            {/* Bottom section */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", borderTop: "2px solid #E5E7EB" }}>

              {/* Deliverables / Forecast / Risk */}
              <div style={{ borderRight: "1px solid #E5E7EB" }}>
                {[
                  { label: "SUMMARY DELIVERABLES", data: deliverables, setter: setDeliverables },
                  { label: "FORECAST", data: forecast, setter: setForecast },
                  { label: "RISK", data: risks, setter: setRisks },
                ].map(({ label, data, setter }) => (
                  <div key={label} style={{ display: "flex", borderBottom: "1px solid #E5E7EB" }}>
                    <div style={{
                      writingMode: "vertical-rl", textOrientation: "mixed",
                      transform: "rotate(180deg)",
                      fontSize: 10, fontWeight: 700, color: "#6B7280", letterSpacing: "0.1em",
                      padding: "12px 8px", borderRight: "1px solid #E5E7EB",
                      background: "#F9FAFB", display: "flex", alignItems: "center",
                    }}>
                      {label}
                    </div>
                    <div style={{ flex: 1, padding: "10px 14px" }}>
                      {data.map((item, i) => (
                        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                          <span style={{ fontSize: 12, color: "#9CA3AF", minWidth: 14 }}>{i + 1}.</span>
                          <InlineEdit
                            value={item}
                            placeholder="—"
                            onSave={v => setter(prev => prev.map((x, j) => j === i ? v : x))}
                            style={{ fontSize: 12, color: "#374151", flex: 1 }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {/* Team + Legend */}
              <div>
                <div style={{ padding: "12px 16px", borderBottom: "1px solid #E5E7EB" }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "#6B7280", marginBottom: 10 }}># PEOPLE WORKING ON PROJECT</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px" }}>
                    <span style={{ fontSize: 12, color: "#6B7280" }}>Project Leader</span>
                    <InlineEdit value={project.leader} placeholder="—" onSave={v => setProject(p => ({ ...p, leader: v }))} style={{ fontSize: 12, color: "#374151" }} />
                    {team.slice(0, 5).map((m, i) => (
                      <>
                        <span key={`l${i}`} style={{ fontSize: 12, color: "#9CA3AF" }}>{m.slot}</span>
                        <InlineEdit
                          key={`v${i}`}
                          value={m.name}
                          placeholder="—"
                          onSave={v => setTeam(prev => prev.map((t, j) => j === i ? { ...t, name: v } : t))}
                          style={{ fontSize: 12, color: "#374151" }}
                        />
                      </>
                    ))}
                  </div>
                </div>
                <div style={{ padding: "12px 16px" }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: "#6B7280", marginBottom: 10 }}>STATUS LEGEND</div>
                  {Object.entries(STATUS_CONFIG).filter(([k]) => k !== "empty").map(([key, cfg]) => (
                    <div key={key} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                      <div style={{ width: 24, height: 12, borderRadius: 3, background: cfg.color }} />
                      <span style={{ fontSize: 12, color: "#374151" }}>{cfg.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* AI Chat Panel */}
        {chatOpen && (
          <div style={{
            width: 360, background: "#fff", borderLeft: "1px solid #E5E7EB",
            display: "flex", flexDirection: "column", height: "100%",
            animation: "slideIn 0.2s ease",
          }}>
            <style>{`
              @keyframes slideIn { from { transform: translateX(20px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
              @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
            `}</style>

            {/* Chat header */}
            <div style={{ padding: "14px 16px", borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#EFF6FF", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontSize: 14 }}>✦</span>
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>OPPM AI</div>
                  <div style={{ fontSize: 11, color: "#22C55E" }}>● Online</div>
                </div>
              </div>
              <button onClick={() => setChatOpen(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", fontSize: 18 }}>×</button>
            </div>

            {/* Quick actions */}
            <div style={{ padding: "10px 12px", borderBottom: "1px solid #F3F4F6", display: "flex", gap: 6, flexWrap: "wrap" }}>
              {["What's at risk?", "Plan W5–W8", "Add objective", "Weekly summary"].map(q => (
                <button
                  key={q}
                  onClick={() => { setInput(q); setTimeout(() => inputRef.current?.focus(), 50); }}
                  style={{ background: "#F3F4F6", border: "none", borderRadius: 16, padding: "4px 10px", fontSize: 11, color: "#374151", cursor: "pointer" }}
                >
                  {q}
                </button>
              ))}
            </div>

            {/* Messages */}
            <div style={{ flex: 1, overflowY: "auto", padding: "14px 12px" }}>
              {messages.map((msg, i) => <ChatMessage key={i} msg={msg} />)}
              {loading && (
                <div style={{ display: "flex", gap: 4, padding: "8px 0", paddingLeft: 4 }}>
                  {[0, 1, 2].map(i => (
                    <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "#3B82F6", animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }} />
                  ))}
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div style={{ padding: "10px 12px", borderTop: "1px solid #E5E7EB" }}>
              <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
                  placeholder="Ask about your project or request changes..."
                  rows={2}
                  style={{
                    flex: 1, resize: "none",
                    background: "#F9FAFB", border: "1px solid #E5E7EB",
                    borderRadius: 10, padding: "8px 12px",
                    fontSize: 13, color: "#111827", outline: "none",
                    fontFamily: "inherit", lineHeight: 1.5,
                  }}
                />
                <button
                  onClick={sendMessage}
                  disabled={loading || !input.trim()}
                  style={{
                    background: input.trim() && !loading ? "#3B82F6" : "#E5E7EB",
                    border: "none", borderRadius: 10,
                    width: 38, height: 38, cursor: input.trim() && !loading ? "pointer" : "not-allowed",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    transition: "background 0.15s", flexShrink: 0,
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={input.trim() && !loading ? "#fff" : "#9CA3AF"} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/>
                  </svg>
                </button>
              </div>
              <div style={{ fontSize: 11, color: "#9CA3AF", marginTop: 5, textAlign: "center" }}>
                Enter to send · Shift+Enter for new line
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}