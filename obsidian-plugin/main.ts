/**
 * 第二大脑 (dierdanao) Obsidian Plugin
 *
 * Features:
 * - Review sidebar: approve/reject LLM tag suggestions
 * - Chat panel: RAG + Agent conversation
 * - Semantic search: Command palette search modal
 * - Settings: configure backend connection
 */

import { Plugin, WorkspaceLeaf, Notice } from "obsidian";
import { DierdanaoSettingTab } from "./src/settings";
import { ReviewView, REVIEW_VIEW_TYPE } from "./src/review-view";
import { ChatView, CHAT_VIEW_TYPE } from "./src/chat-view";
import { SearchModal } from "./src/search-modal";
import {
  setApiSettings,
  healthApi,
  reviewApi,
  type PluginSettings,
  DEFAULT_SETTINGS,
} from "./src/api";

export default class DierdanaoPlugin extends Plugin {
  settings: PluginSettings = { ...DEFAULT_SETTINGS };
  private statusBarItem: HTMLElement | null = null;
  private syncInterval: number | null = null;

  async onload() {
    await this.loadSettings();
    setApiSettings(this.settings);

    // Register views
    this.registerView(REVIEW_VIEW_TYPE, (leaf) => new ReviewView(leaf));
    this.registerView(CHAT_VIEW_TYPE, (leaf) => new ChatView(leaf));

    // Settings tab
    this.addSettingTab(new DierdanaoSettingTab(this.app, this));

    // Ribbon icons
    this.addRibbonIcon("clipboard-check", "审核队列", () => {
      this.activateView(REVIEW_VIEW_TYPE);
    });

    this.addRibbonIcon("message-square", "智能对话", () => {
      this.activateView(CHAT_VIEW_TYPE);
    });

    // Commands
    this.addCommand({
      id: "open-review",
      name: "打开审核队列",
      callback: () => this.activateView(REVIEW_VIEW_TYPE),
    });

    this.addCommand({
      id: "open-chat",
      name: "打开智能对话",
      callback: () => this.activateView(CHAT_VIEW_TYPE),
    });

    this.addCommand({
      id: "semantic-search",
      name: "语义搜索",
      callback: () => new SearchModal(this.app).open(),
    });

    this.addCommand({
      id: "check-connection",
      name: "检查后端连接",
      callback: async () => {
        try {
          const h = await healthApi.check();
          new Notice(`后端已连接 (v${h.version})`);
        } catch (e) {
          new Notice(`后端连接失败: ${e}`);
        }
      },
    });

    this.addCommand({
      id: "refresh-review",
      name: "刷新审核队列",
      callback: async () => {
        const leaves = this.app.workspace.getLeavesOfType(REVIEW_VIEW_TYPE);
        for (const leaf of leaves) {
          (leaf.view as ReviewView).refresh();
        }
      },
    });

    this.addCommand({
      id: "ask-about-selection",
      name: "问第二大脑（基于选中文本）",
      editorCallback: async (editor) => {
        const selection = editor.getSelection();
        if (!selection) {
          new Notice("请先选中一些文本");
          return;
        }
        await this.activateView(CHAT_VIEW_TYPE);
        // Give the view time to render, then we can't directly set input
        // but at least the view is ready for manual input
        new Notice(`已打开对话面板，可基于选中内容提问`);
      },
    });

    // Status bar
    this.statusBarItem = this.addStatusBarItem();
    this.updateStatusBar();

    // Auto-sync check
    if (this.settings.syncOnStartup) {
      setTimeout(() => this.checkBackendAndNotify(), 3000);
    }

    // Periodic review count update
    this.registerInterval(
      window.setInterval(() => this.updateStatusBar(), 60000)
    );
  }

  onunload() {
    // Views are automatically cleaned up by Obsidian
  }

  async loadSettings() {
    this.settings = Object.assign(
      {},
      DEFAULT_SETTINGS,
      await this.loadData()
    );
  }

  async saveSettings() {
    await this.saveData(this.settings);
    setApiSettings(this.settings);
  }

  private async activateView(viewType: string) {
    const { workspace } = this.app;

    let leaf: WorkspaceLeaf | null = null;
    const leaves = workspace.getLeavesOfType(viewType);

    if (leaves.length > 0) {
      leaf = leaves[0];
    } else {
      leaf = workspace.getRightLeaf(false);
      if (leaf) {
        await leaf.setViewState({ type: viewType, active: true });
      }
    }

    if (leaf) {
      workspace.revealLeaf(leaf);
    }
  }

  private async updateStatusBar() {
    if (!this.statusBarItem) return;
    try {
      const { count } = await reviewApi.getCount();
      this.statusBarItem.setText(
        count > 0 ? `🧠 审核: ${count}` : "🧠 第二大脑"
      );
    } catch {
      this.statusBarItem.setText("🧠 离线");
    }
  }

  private async checkBackendAndNotify() {
    try {
      const h = await healthApi.check();
      const { count } = await reviewApi.getCount();
      if (count > 0) {
        new Notice(`第二大脑已连接 (v${h.version})，有 ${count} 条待审核`);
      }
    } catch {
      // Silent fail on startup
    }
  }
}
