/**
 * Review sidebar: inspect and approve/reject LLM tag suggestions within Obsidian.
 */

import { ItemView, WorkspaceLeaf, Notice, setIcon } from "obsidian";
import { reviewApi, type ReviewItem } from "./api";

export const REVIEW_VIEW_TYPE = "dierdanao-review";

export class ReviewView extends ItemView {
  private items: ReviewItem[] = [];
  private loading = false;

  constructor(leaf: WorkspaceLeaf) {
    super(leaf);
  }

  getViewType(): string {
    return REVIEW_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "审核队列";
  }

  getIcon(): string {
    return "clipboard-check";
  }

  async onOpen() {
    await this.refresh();
  }

  async refresh() {
    this.loading = true;
    this.render();
    try {
      this.items = await reviewApi.listPending();
    } catch (e) {
      new Notice(`加载审核队列失败: ${e}`);
      this.items = [];
    }
    this.loading = false;
    this.render();
  }

  private render() {
    const container = this.containerEl.children[1] as HTMLElement;
    container.empty();

    // Header
    const header = container.createDiv({ cls: "nav-header" });
    header.createEl("h4", {
      text: `审核队列 (${this.items.length})`,
      cls: "nav-header-title",
    });
    const refreshBtn = header.createEl("button", {
      cls: "clickable-icon nav-action-button",
      attr: { "aria-label": "刷新" },
    });
    setIcon(refreshBtn, "refresh-cw");
    refreshBtn.addEventListener("click", () => this.refresh());

    if (this.loading) {
      container.createEl("p", {
        text: "加载中...",
        cls: "pane-empty",
      });
      return;
    }

    if (this.items.length === 0) {
      container.createEl("p", {
        text: "没有待审核的项目",
        cls: "pane-empty",
      });
      return;
    }

    const list = container.createDiv({ cls: "dierdanao-review-list" });

    for (const item of this.items) {
      const card = list.createDiv({ cls: "dierdanao-review-card" });

      // Title
      card.createEl("div", {
        text: item.entity_title || "无标题",
        cls: "dierdanao-review-title",
      });

      // Source + Date
      const meta = card.createDiv({ cls: "dierdanao-review-meta" });
      meta.createEl("span", {
        text: item.entity_source || "unknown",
        cls: "dierdanao-review-source",
      });
      if (item.created_at) {
        meta.createEl("span", {
          text: new Date(item.created_at).toLocaleDateString(),
          cls: "dierdanao-review-date",
        });
      }

      // Content preview
      if (item.entity_content) {
        card.createEl("div", {
          text: item.entity_content.slice(0, 120) + (item.entity_content.length > 120 ? "..." : ""),
          cls: "dierdanao-review-content",
        });
      }

      // Suggested tags
      const tagsDiv = card.createDiv({ cls: "dierdanao-review-tags" });
      if (item.suggested_folder_tags?.length) {
        tagsDiv.createEl("span", { text: "文件夹: ", cls: "dierdanao-tag-label" });
        for (const t of item.suggested_folder_tags) {
          tagsDiv.createEl("span", { text: t, cls: "dierdanao-tag folder" });
        }
      }
      if (item.suggested_content_tags?.length) {
        tagsDiv.createEl("span", { text: "标签: ", cls: "dierdanao-tag-label" });
        for (const t of item.suggested_content_tags) {
          tagsDiv.createEl("span", { text: t, cls: "dierdanao-tag content" });
        }
      }

      // Action buttons
      const actions = card.createDiv({ cls: "dierdanao-review-actions" });

      const approveBtn = actions.createEl("button", {
        text: "通过",
        cls: "dierdanao-btn approve",
      });
      approveBtn.addEventListener("click", async () => {
        try {
          await reviewApi.approve(item.id);
          new Notice(`已通过: ${item.entity_title}`);
          this.items = this.items.filter((i) => i.id !== item.id);
          this.render();
        } catch (e) {
          new Notice(`审核失败: ${e}`);
        }
      });

      const rejectBtn = actions.createEl("button", {
        text: "拒绝",
        cls: "dierdanao-btn reject",
      });
      rejectBtn.addEventListener("click", async () => {
        try {
          await reviewApi.reject(item.id, "从 Obsidian 拒绝");
          new Notice(`已拒绝: ${item.entity_title}`);
          this.items = this.items.filter((i) => i.id !== item.id);
          this.render();
        } catch (e) {
          new Notice(`拒绝失败: ${e}`);
        }
      });
    }
  }
}
