import { useEffect, useState } from 'react';
import { syncApi, type SyncStatus } from '../api/client';
import { Settings as SettingsIcon, Save } from 'lucide-react';

export default function Settings() {
  const [syncConfig, setSyncConfig] = useState<SyncStatus['config'] | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    syncApi.getStatus().then(s => setSyncConfig(s.config)).catch(() => {});
  }, []);

  const handleSave = async () => {
    if (!syncConfig) return;
    setSaving(true);
    setMessage('');
    try {
      await syncApi.updateConfig({
        enabled: syncConfig.enabled,
        auto_sync: syncConfig.auto_sync,
        interval_minutes: syncConfig.interval_minutes,
        sources: syncConfig.sources,
      });
      setMessage('配置已保存');
    } catch (e: unknown) {
      setMessage(e instanceof Error ? e.message : '保存失败');
    }
    setSaving(false);
  };

  if (!syncConfig) {
    return <div className="p-6 max-w-4xl mx-auto text-gray-400">加载中...</div>;
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <SettingsIcon className="w-6 h-6" /> 系统设置
      </h1>

      {/* Apple Sync Settings */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">Apple 同步配置</h2>

        <div className="space-y-4">
          <label className="flex items-center justify-between">
            <span className="text-sm text-gray-700">启用 Apple 同步</span>
            <input
              type="checkbox"
              checked={syncConfig.enabled}
              onChange={e => setSyncConfig({ ...syncConfig, enabled: e.target.checked })}
              className="rounded"
            />
          </label>

          <label className="flex items-center justify-between">
            <span className="text-sm text-gray-700">自动定时同步</span>
            <input
              type="checkbox"
              checked={syncConfig.auto_sync}
              onChange={e => setSyncConfig({ ...syncConfig, auto_sync: e.target.checked })}
              className="rounded"
            />
          </label>

          <label className="flex items-center justify-between">
            <span className="text-sm text-gray-700">同步间隔（分钟）</span>
            <input
              type="number"
              min={5}
              max={1440}
              value={syncConfig.interval_minutes}
              onChange={e => setSyncConfig({ ...syncConfig, interval_minutes: parseInt(e.target.value) || 30 })}
              className="w-24 px-3 py-1.5 border border-gray-200 rounded-lg text-sm text-right outline-none focus:ring-1 focus:ring-blue-400"
            />
          </label>

          <div className="border-t border-gray-100 pt-4">
            <p className="text-sm font-medium text-gray-700 mb-3">同步数据源</p>
            {[
              { key: 'notes', label: '备忘录 (Apple Notes)' },
              { key: 'reminders', label: '待办事项 (Apple Reminders)' },
              { key: 'calendar', label: '日历 (Apple Calendar)' },
            ].map(({ key, label }) => (
              <label key={key} className="flex items-center justify-between py-2">
                <span className="text-sm text-gray-600">{label}</span>
                <input
                  type="checkbox"
                  checked={syncConfig.sources[key] !== false}
                  onChange={e => setSyncConfig({
                    ...syncConfig,
                    sources: { ...syncConfig.sources, [key]: e.target.checked },
                  })}
                  className="rounded"
                />
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* System Info */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">系统信息</h2>
        <div className="space-y-2 text-sm text-gray-600">
          <p>版本: v0.2.0 (Phase 2)</p>
          <p>LLM API: 由 .env 中 LLM_API_URL 配置</p>
          <p>Obsidian Vault: 由 .env 中 OBSIDIAN_VAULT_PATH 配置</p>
          <p className="text-xs text-gray-400 mt-2">更多配置请编辑 backend/config/user_config.yaml</p>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          <Save className="w-4 h-4" /> {saving ? '保存中...' : '保存配置'}
        </button>
        {message && <span className={`text-sm ${message.includes('失败') ? 'text-red-500' : 'text-green-500'}`}>{message}</span>}
      </div>
    </div>
  );
}
