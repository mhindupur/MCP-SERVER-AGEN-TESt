"use client";

import { useEffect, useMemo, useState } from "react";

type Conversation = { id: string; title: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export default function HomePage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string>("");
  const [message, setMessage] = useState<string>("List AWS EC2 instances with less than 2GB memory");
  const [awsRoleArn, setAwsRoleArn] = useState<string>("");
  const [awsRegion, setAwsRegion] = useState<string>("ap-south-1");
  const [trace, setTrace] = useState<any[] | null>(null);
  const [reply, setReply] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);
  const [me, setMe] = useState<{ id: string; email: string; name?: string | null } | null>(null);

  const loginUrl = useMemo(() => {
    const next = `${window.location.origin}/`;
    return `${API_BASE}/auth/login?next=${encodeURIComponent(next)}`;
  }, []);

  async function refreshMe() {
    const r = await fetch(`${API_BASE}/me`, { credentials: "include" });
    if (!r.ok) {
      setMe(null);
      return;
    }
    setMe(await r.json());
  }

  async function refreshConversations() {
    const r = await fetch(`${API_BASE}/conversations`, { credentials: "include" });
    if (!r.ok) return;
    const rows: Conversation[] = await r.json();
    setConversations(rows);
    if (!conversationId && rows[0]?.id) setConversationId(rows[0].id);
  }

  useEffect(() => {
    void refreshMe();
    void refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function createConversation() {
    const r = await fetch(`${API_BASE}/conversations`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "New chat" })
    });
    if (!r.ok) return;
    const conv = await r.json();
    setConversationId(conv.id);
    await refreshConversations();
  }

  async function sendChat() {
    if (!conversationId) return;
    setBusy(true);
    setTrace([]);
    setReply("");
    try {
      const r = await fetch(`${API_BASE}/chat/stream`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream"
        },
        body: JSON.stringify({
          conversation_id: conversationId,
          message,
          aws_role_arn: awsRoleArn || null,
          aws_region: awsRegion
        })
      });

      if (!r.ok || !r.body) {
        const text = await r.text();
        setReply(`Error (${r.status}): ${text}`);
        return;
      }

      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const steps: any[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by a blank line.
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const lines = part.split("\n").filter(Boolean);
          let event = "message";
          let dataLine: string | null = null;
          for (const line of lines) {
            if (line.startsWith("event:")) event = line.slice("event:".length).trim();
            if (line.startsWith("data:")) dataLine = line.slice("data:".length).trim();
          }
          if (!dataLine) continue;
          const payload = JSON.parse(dataLine);

          if (event === "trace" && payload?.step) {
            steps.push(payload.step);
            setTrace([...steps]);
          }
          if (event === "final") {
            setReply(String(payload.reply || ""));
            if (Array.isArray(payload.trace)) setTrace(payload.trace);
          }
          if (event === "error") {
            setReply(`Error: ${String(payload.message || "unknown")}`);
          }
        }
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <div style={{ fontSize: 18, fontWeight: 650 }}>Team Web IDE (MCP + OpenAI)</div>
          <div className="muted" style={{ marginTop: 6 }}>
            Login via SSO, then chat. Tool traces appear on the right.
          </div>
        </div>
        <div className="row">
          {me ? (
            <div className="muted">
              Signed in as <span className="mono">{me.email}</span>
            </div>
          ) : (
            <a href={loginUrl}>
              <button type="button">Sign in (OIDC)</button>
            </a>
          )}
        </div>
      </div>

      <div style={{ height: 14 }} />

      <div className="row">
        <div style={{ flex: "1 1 360px" }} className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div style={{ fontWeight: 650 }}>Conversation</div>
            <button type="button" onClick={() => void createConversation()} disabled={!me}>
              New
            </button>
          </div>

          <div style={{ height: 10 }} />

          <label className="muted" htmlFor="conv">
            Active chat
          </label>
          <select
            id="conv"
            value={conversationId}
            onChange={(e) => setConversationId(e.target.value)}
            style={{
              width: "100%",
              marginTop: 8,
              padding: "10px 12px",
              borderRadius: 10,
              border: "1px solid var(--border)",
              background: "rgba(10, 14, 24, 0.55)",
              color: "var(--text)"
            }}
          >
            {conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} ({c.id.slice(0, 8)}…)
              </option>
            ))}
          </select>

          <div style={{ height: 12 }} />

          <label className="muted" htmlFor="role">
            AWS role ARN (optional if deployment default mapping applies)
          </label>
          <input id="role" value={awsRoleArn} onChange={(e) => setAwsRoleArn(e.target.value)} placeholder="arn:aws:iam::..." />

          <div style={{ height: 12 }} />

          <label className="muted" htmlFor="region">
            AWS region
          </label>
          <input id="region" value={awsRegion} onChange={(e) => setAwsRegion(e.target.value)} />

          <div style={{ height: 12 }} />

          <label className="muted" htmlFor="msg">
            Message
          </label>
          <textarea id="msg" rows={6} value={message} onChange={(e) => setMessage(e.target.value)} />

          <div style={{ height: 12 }} />

          <button type="button" onClick={() => void sendChat()} disabled={busy || !me || !conversationId}>
            {busy ? "Running…" : "Send"}
          </button>

          <div style={{ height: 14 }} />

          <div style={{ fontWeight: 650, marginBottom: 8 }}>Assistant</div>
          <div className="mono">{reply || "—"}</div>
        </div>

        <div style={{ flex: "1 1 420px" }} className="card">
          <div style={{ fontWeight: 650, marginBottom: 8 }}>Tool trace</div>
          {!trace || trace.length === 0 ? (
            <div className="muted">No trace yet.</div>
          ) : (
            <div className="mono">{JSON.stringify(trace, null, 2)}</div>
          )}
        </div>
      </div>
    </div>
  );
}
