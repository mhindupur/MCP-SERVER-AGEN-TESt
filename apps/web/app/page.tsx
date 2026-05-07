"use client";

import { useEffect, useRef, useState } from "react";

type Conversation = { id: string; title: string };
type ChatMessage = { id: string; role: string; content: any; created_at: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8002";
const AUTH_DISABLED = process.env.NEXT_PUBLIC_AUTH_DISABLED === "true";

export default function HomePage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState<string>("List AWS EC2 instances with less than 2GB memory");
  const [awsRoleArn, setAwsRoleArn] = useState<string>("");
  const [awsRegion, setAwsRegion] = useState<string>("ap-south-1");
  const [trace, setTrace] = useState<any[] | null>(null);
  const [reply, setReply] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);
  const [me, setMe] = useState<{ id: string; email: string; name?: string | null } | null>(null);

  const [loginUrl, setLoginUrl] = useState<string>("");
  const historyRef = useRef<HTMLDivElement | null>(null);
  const traceRef = useRef<HTMLDivElement | null>(null);

  const lastAssistantId = (() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i]?.role === "assistant") return messages[i].id;
    }
    return null;
  })();

  async function refreshMe() {
    const r = await fetch(`/api/me`, { credentials: "include" });
    if (!r.ok) {
      setMe(null);
      return;
    }
    setMe(await r.json());
  }

  async function refreshConversations() {
    const r = await fetch(`/api/conversations`, { credentials: "include" });
    if (!r.ok) return;
    const rows: Conversation[] = await r.json();
    setConversations(rows);
    if (!conversationId && rows[0]?.id) setConversationId(rows[0].id);
  }

  async function refreshMessages(convId: string) {
    if (!convId) return;
    const r = await fetch(`/api/conversations/${convId}/messages`, { credentials: "include" });
    if (!r.ok) return;
    const rows: ChatMessage[] = await r.json();
    setMessages(rows);
  }

  useEffect(() => {
    // `window` is only available on the client.
    setLoginUrl(`${API_BASE}/auth/login?next=${encodeURIComponent(window.location.origin + "/")}`);
    void refreshMe();
    void refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void refreshMessages(conversationId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  useEffect(() => {
    // Keep newest messages visible at bottom (ChatGPT/Cursor style)
    const el = historyRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  useEffect(() => {
    // Auto-scroll trace output like a log tail.
    const el = traceRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [trace?.length]);

  async function createConversation() {
    const r = await fetch(`/api/conversations`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "New chat" })
    });
    if (!r.ok) return;
    const conv = await r.json();
    setConversationId(conv.id);
    await refreshConversations();
    await refreshMessages(conv.id);
  }

  async function sendChat() {
    if (!conversationId) return;
    if (!awsRoleArn.trim()) {
      setReply("Error: AWS role ARN is required.");
      return;
    }
    setBusy(true);
    setTrace([]);
    setReply("");
    try {
      const r = await fetch(`/api/chat/stream`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream"
        },
        body: JSON.stringify({
          conversation_id: conversationId,
          message,
          aws_role_arn: awsRoleArn.trim(),
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
            await refreshMessages(conversationId);
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

  function renderMessage(m: ChatMessage) {
    const text = m?.content?.text ?? "";
    const traceSteps = m?.content?.trace;
    const isUser = m.role === "user";
    const isMostRecentAssistant = m.role === "assistant" && lastAssistantId === m.id;
    const isCollapsedByDefault = m.role === "assistant" && !isMostRecentAssistant;
    return (
      <div
        key={m.id}
        className={`msgRow ${isUser ? "msgRowUser" : "msgRowAssistant"}`}
      >
        <div className={`msgBubble ${isUser ? "msgBubbleUser" : "msgBubbleAssistant"}`}>
          <div className="msgMeta">
            <div className="msgTitle">{isUser ? "You" : "Assistant"}</div>
            <div className="muted mono">{new Date(m.created_at).toLocaleString()}</div>
          </div>
          <div style={{ height: 8 }} />
          {m.role === "assistant" ? (
            <details open={!isCollapsedByDefault}>
              <summary className="muted msgSummary">
                {isMostRecentAssistant ? "Assistant (latest)" : "Assistant"}
              </summary>
              <div style={{ height: 8 }} />
              <div className="mono">{text || "—"}</div>
              {Array.isArray(traceSteps) && traceSteps.length > 0 ? (
                <>
                  <div style={{ height: 10 }} />
                  <details>
                    <summary className="muted msgSummary">Tool calls ({traceSteps.length})</summary>
                    <div style={{ height: 6 }} />
                    <div className="mono">{JSON.stringify(traceSteps, null, 2)}</div>
                  </details>
                </>
              ) : null}
            </details>
          ) : (
            <div className="mono">{text || "—"}</div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="appShell">
      <div className="topBar">
        <div>
          <div className="topBarTitle">Team Web IDE (MCP + OpenAI)</div>
          <div className="muted" style={{ marginTop: 4, fontSize: 12 }}>
            Login via SSO, then chat. Tool trace appears on the right.
          </div>
        </div>
        <div className="row">
          {me ? (
            <div className="muted">
              Signed in as <span className="mono">{me.email}</span>
            </div>
          ) : AUTH_DISABLED ? (
            <div className="muted">
              Dev mode enabled (auth bypass). Refreshing user…
            </div>
          ) : (
            <a href={loginUrl}>
              <button type="button">Sign in (OIDC)</button>
            </a>
          )}
        </div>
      </div>

      <div className="mainGrid">
        <div className="pane leftPane">
          <div className="paneHeader">
            <div className="paneHeaderTitle">Conversation</div>
            <button type="button" onClick={() => void createConversation()} disabled={!me && !AUTH_DISABLED}>
              New
            </button>
          </div>

          <label className="fieldLabel" htmlFor="conv">
            Active chat
          </label>
          <select id="conv" value={conversationId} onChange={(e) => setConversationId(e.target.value)}>
            {conversations.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} ({c.id.slice(0, 8)}…)
              </option>
            ))}
          </select>

          <div
            ref={historyRef}
            className="scrollPane messagesPane"
          >
            {!messages || messages.length === 0 ? (
              <div className="muted">No messages yet. Click New and send a message.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", justifyContent: "flex-end", minHeight: "100%" }}>
                {messages.map(renderMessage)}
              </div>
            )}
          </div>

          <div className="stickyBottom composer">
            <label className="fieldLabel" htmlFor="msg" style={{ marginTop: 0 }}>
              Message
            </label>
            <textarea id="msg" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} />

            <div style={{ height: 10 }} />

            <div className="composerRow">
              <div className="composerRole">
                <label className="fieldLabel" htmlFor="role" style={{ marginTop: 0 }}>
                  AWS role ARN
                </label>
                <input
                  id="role"
                  value={awsRoleArn}
                  onChange={(e) => setAwsRoleArn(e.target.value)}
                  placeholder="arn:aws:iam::123456789012:role/..."
                />
              </div>
              <div className="composerRegion">
                <label className="fieldLabel" htmlFor="region" style={{ marginTop: 0 }}>
                  AWS region
                </label>
                <input id="region" value={awsRegion} onChange={(e) => setAwsRegion(e.target.value)} />
              </div>
              <div className="composerSend" style={{ marginLeft: "auto" }}>
                <button
                  type="button"
                  onClick={() => void sendChat()}
                  disabled={busy || (!me && !AUTH_DISABLED) || !conversationId || !awsRoleArn.trim()}
                >
                  {busy ? "Running…" : "Send"}
                </button>
              </div>
            </div>

            {reply && reply.startsWith("Error") ? <div className="composerError">{reply}</div> : null}
          </div>
        </div>

        <div className="pane rightPane">
          <div className="traceHeader">Live tool trace</div>
          <div ref={traceRef} className="scrollPane" style={{ flex: "1 1 auto", paddingRight: 6 }}>
            {!trace || trace.length === 0 ? (
              <div className="muted">
                No tool calls yet. Send a message to see tool execution and results here.
              </div>
            ) : (
              <div className="mono">{JSON.stringify(trace, null, 2)}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
