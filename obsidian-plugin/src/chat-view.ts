/**
 * Chat sidebar: RAG/Agent conversation panel within Obsidian right sidebar.
 */

import { ItemView, WorkspaceLeaf, Notice, setIcon } from "obsidian";
import { chatApi, type ChatResponse } from "./api";

export const CHAT_VIEW_TYPE = "dierdanao-chat";

interface DisplayMsg {
  role: "user" | "assistant";
  content: string;
  sources?: { index: number; title: string; source: string }[];
  toolCalls?: { tool: string; arguments: Record<string, unknown> }[];
}

export class ChatView extends ItemView {
  private messages: DisplayMsg[] = [];
  private conversationId: string | null = null;
  private mode: "rag" | "agent" = "rag";
  private loading = false;

  constructor(leaf: WorkspaceLeaf) {
    super(leaf);
  }

  getViewType(): string {
    return CHAT_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "智能对话";
  }

  getIcon(): string {
    return "message-square";
  }

  async onOpen() {
    this.render();
  }

  private render() {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();
    container.addClass("dierdanao-chat-container");

    // Header
    const header = container.createDiv({ cls: "dierdanao-chat-header" });
    header.createEl("h4", { text: "智能对话" });

    // Mode toggle
    const modeBar = header.createDiv({ cls: "dierdanao-chat-mode" });
    const ragBtn = modeBar.createEl("button", {
      text: "RAG",
      cls: `dierdanao-mode-btn ${this.mode === "rag" ? "active" : ""}`,
    });
    ragBtn.addEventListener("click", () => {
      this.mode = "rag";
      this.render();
    });
    const agentBtn = modeBar.createEl("button", {
      text: "Agent",
      cls: `dierdanao-mode-btn ${this.mode === "agent" ? "active" : ""}`,
    });
    agentBtn.addEventListener("click", () => {
      this.mode = "agent";
      this.render();
    });

    // New conversation button
    const newBtn = header.createEl("button", {
      cls: "clickable-icon",
      attr: { "aria-label": "新对话" },
    });
    setIcon(newBtn, "plus");
    newBtn.addEventListener("click", () => {
      this.messages = [];
      this.conversationId = null;
      this.render();
    });

    // Messages area
    const messagesArea = container.createDiv({ cls: "dierdanao-chat-messages" });

    if (this.messages.length === 0) {
      const empty = messagesArea.createDiv({ cls: "dierdanao-chat-empty" });
      empty.createEl("p", {
        text: this.mode === "rag" ? "基于知识库的问答" : "Agent 可以搜索、创建、打标签",
      });
    }

    for (const msg of this.messages) {
      const bubble = messagesArea.createDiv({
        cls: `dierdanao-chat-msg ${msg.role}`,
      });

      if (msg.toolCalls?.length) {
        const tcDiv = bubble.createDiv({ cls: "dierdanao-chat-tools" });
        for (const tc of msg.toolCalls) {
          const toolEl = tcDiv.createDiv({ cls: "dierdanao-tool-call" });
          setIcon(toolEl.createSpan(), "wrench");
          toolEl.createSpan({ text: ` ${tc.tool}` });
        }
      }

      bubble.createDiv({ text: msg.content, cls: "dierdanao-chat-text" });

      if (msg.sources?.length) {
        const srcDiv = bubble.createDiv({ cls: "dierdanao-chat-sources" });
        srcDiv.createEl("small", { text: "引用:" });
        for (const s of msg.sources) {
          srcDiv.createEl("small", {
            text: ` [${s.index}] ${s.title}`,
            cls: "dierdanao-source-ref",
          });
        }
      }
    }

    if (this.loading) {
      messagesArea.createDiv({
        text: this.mode === "agent" ? "Agent 思考中..." : "检索中...",
        cls: "dierdanao-chat-loading",
      });
    }

    // Scroll to bottom
    messagesArea.scrollTop = messagesArea.scrollHeight;

    // Input area
    const inputArea = container.createDiv({ cls: "dierdanao-chat-input" });
    const input = inputArea.createEl("input", {
      type: "text",
      placeholder: this.mode === "agent" ? "让 Agent 帮你..." : "向知识库提问...",
      cls: "dierdanao-chat-input-field",
    });
    const sendBtn = inputArea.createEl("button", { cls: "dierdanao-chat-send" });
    setIcon(sendBtn, "send");

    const doSend = async () => {
      const q = input.value.trim();
      if (!q || this.loading) return;
      input.value = "";

      this.messages.push({ role: "user", content: q });
      this.loading = true;
      this.render();

      try {
        const resp: ChatResponse = await chatApi.send(
          q,
          this.conversationId || undefined,
          this.mode
        );
        this.conversationId = resp.conversation_id;
        this.messages.push({
          role: "assistant",
          content: resp.answer,
          sources: resp.sources,
          toolCalls: resp.tool_calls as DisplayMsg["toolCalls"],
        });
      } catch (e) {
        this.messages.push({
          role: "assistant",
          content: `错误: ${e}`,
        });
      }
      this.loading = false;
      this.render();
    };

    sendBtn.addEventListener("click", doSend);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") doSend();
    });
  }
}
