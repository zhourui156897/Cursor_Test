/**
 * Semantic search modal: fuzzy/semantic search across the knowledge base.
 */

import { App, Modal, Notice, setIcon } from "obsidian";
import { searchApi, type SearchResult } from "./api";

export class SearchModal extends Modal {
  private results: SearchResult[] = [];
  private query = "";
  private searching = false;

  constructor(app: App) {
    super(app);
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.addClass("dierdanao-search-modal");

    contentEl.createEl("h3", { text: "语义搜索" });

    const form = contentEl.createDiv({ cls: "dierdanao-search-form" });
    const input = form.createEl("input", {
      type: "text",
      placeholder: "输入自然语言查询...",
      cls: "dierdanao-search-input",
    });
    const searchBtn = form.createEl("button", {
      text: "搜索",
      cls: "dierdanao-btn approve",
    });

    const resultsDiv = contentEl.createDiv({ cls: "dierdanao-search-results" });

    const doSearch = async () => {
      this.query = input.value.trim();
      if (!this.query) return;
      this.searching = true;
      resultsDiv.empty();
      resultsDiv.createEl("p", { text: "搜索中..." });

      try {
        const resp = await searchApi.search(this.query, 10);
        this.results = resp.results;
        resultsDiv.empty();

        if (this.results.length === 0) {
          resultsDiv.createEl("p", {
            text: "未找到相关结果",
            cls: "pane-empty",
          });
          return;
        }

        resultsDiv.createEl("small", {
          text: `找到 ${resp.total} 条结果`,
          cls: "dierdanao-search-count",
        });

        for (const r of this.results) {
          const card = resultsDiv.createDiv({ cls: "dierdanao-search-result" });

          const titleEl = card.createDiv({ cls: "dierdanao-search-result-title" });
          titleEl.createEl("strong", { text: r.title || "无标题" });
          if (r.source) {
            titleEl.createEl("span", {
              text: ` [${r.source}]`,
              cls: "dierdanao-search-result-source",
            });
          }

          if (r.content) {
            card.createEl("div", {
              text: r.content.slice(0, 200) + (r.content.length > 200 ? "..." : ""),
              cls: "dierdanao-search-result-content",
            });
          }

          const meta = card.createDiv({ cls: "dierdanao-search-result-meta" });
          meta.createEl("span", { text: r.match_type });
          if (r.distance !== null) {
            meta.createEl("span", {
              text: `相似度: ${(1 - r.distance).toFixed(3)}`,
            });
          }
        }
      } catch (e) {
        resultsDiv.empty();
        resultsDiv.createEl("p", { text: `搜索失败: ${e}` });
      }
      this.searching = false;
    };

    searchBtn.addEventListener("click", doSearch);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") doSearch();
    });

    input.focus();
  }

  onClose() {
    this.contentEl.empty();
  }
}
