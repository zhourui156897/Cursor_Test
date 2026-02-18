/**
 * Plugin settings tab for configuring the backend connection.
 */

import { App, PluginSettingTab, Setting, Notice } from "obsidian";
import type DierdanaoPlugin from "../main";
import { healthApi, type PluginSettings, DEFAULT_SETTINGS } from "./api";

export class DierdanaoSettingTab extends PluginSettingTab {
  plugin: DierdanaoPlugin;

  constructor(app: App, plugin: DierdanaoPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "第二大脑 - 连接设置" });

    new Setting(containerEl)
      .setName("后端 API 地址")
      .setDesc("第二大脑后端服务地址")
      .addText((text) =>
        text
          .setPlaceholder("http://localhost:8000")
          .setValue(this.plugin.settings.apiUrl)
          .onChange(async (value) => {
            this.plugin.settings.apiUrl = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("用户名")
      .setDesc("登录后端的用户名")
      .addText((text) =>
        text
          .setValue(this.plugin.settings.username)
          .onChange(async (value) => {
            this.plugin.settings.username = value;
            this.plugin.settings.token = "";
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("密码")
      .setDesc("登录后端的密码")
      .addText((text) => {
        text.inputEl.type = "password";
        text
          .setValue(this.plugin.settings.password)
          .onChange(async (value) => {
            this.plugin.settings.password = value;
            this.plugin.settings.token = "";
            await this.plugin.saveSettings();
          });
      });

    new Setting(containerEl)
      .setName("测试连接")
      .setDesc("验证后端连接是否正常")
      .addButton((btn) =>
        btn.setButtonText("测试").onClick(async () => {
          try {
            const h = await healthApi.check();
            new Notice(`连接成功! 后端版本: ${h.version}`);
          } catch (e) {
            new Notice(`连接失败: ${e}`);
          }
        })
      );

    containerEl.createEl("h3", { text: "同步设置" });

    new Setting(containerEl)
      .setName("启动时同步")
      .setDesc("Obsidian 启动时自动从后端同步数据")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.syncOnStartup)
          .onChange(async (value) => {
            this.plugin.settings.syncOnStartup = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("同步间隔（分钟）")
      .setDesc("自动同步间隔，0 表示不自动同步")
      .addText((text) =>
        text
          .setValue(String(this.plugin.settings.syncIntervalMinutes))
          .onChange(async (value) => {
            this.plugin.settings.syncIntervalMinutes =
              parseInt(value) || 0;
            await this.plugin.saveSettings();
          })
      );
  }
}
