import { useEffect, useState, useCallback } from 'react';
import { syncApi, settingsApi, type SyncStatus, type LLMConfigResponse, type SystemInfo } from '../api/client';
import { Settings as SettingsIcon, Save, Cpu, FolderOpen, RefreshCw, Eye, EyeOff, CheckCircle2, XCircle, Database, Brain } from 'lucide-react';

type TabKey = 'llm' | 'sync' | 'paths' | 'system';

export default function Settings() {
  const [tab, setTab] = useState<TabKey>('llm');

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <SettingsIcon className="w-6 h-6" /> 系统设置
      </h1>

      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg">
        {([
          { key: 'llm' as TabKey, label: 'LLM / 模型', icon: Cpu },
          { key: 'sync' as TabKey, label: 'Apple 同步', icon: RefreshCw },
          { key: 'paths' as TabKey, label: '路径配置', icon: FolderOpen },
          { key: 'system' as TabKey, label: '系统信息', icon: Database },
        ]).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              tab === key ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Icon className="w-4 h-4" /> {label}
          </button>
        ))}
      </div>

      {tab === 'llm' && <LLMTab />}
      {tab === 'sync' && <SyncTab />}
      {tab === 'paths' && <PathsTab />}
      {tab === 'system' && <SystemTab />}
    </div>
  );
}

/* ===== LLM / 模型配置 ===== */

function LLMTab() {
  const [config, setConfig] = useState<LLMConfigResponse | null>(null);
  const [form, setForm] = useState({
    api_url: '',
    api_key: '',
    model: '',
    embedding_model: '',
    embedding_dim: 1024,
  });
  const [showKey, setShowKey] = useState(false);
  const [keyEdited, setKeyEdited] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);

  const load = useCallback(async () => {
    try {
      const c = await settingsApi.getLLM();
      setConfig(c);
      setForm({
        api_url: c.api_url,
        api_key: '',
        model: c.model,
        embedding_model: c.embedding_model,
        embedding_dim: c.embedding_dim,
      });
      setKeyEdited(false);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    setSaving(true);
    setMsg(null);
    try {
      const payload: Record<string, unknown> = {
        api_url: form.api_url,
        model: form.model,
        embedding_model: form.embedding_model,
        embedding_dim: form.embedding_dim,
      };
      if (keyEdited && form.api_key) {
        payload.api_key = form.api_key;
      }
      await settingsApi.updateLLM(payload);
      setMsg({ text: '配置已保存', ok: true });
      await load();
    } catch (e: unknown) {
      setMsg({ text: e instanceof Error ? e.message : '保存失败', ok: false });
    }
    setSaving(false);
  };

  const handleTest = async () => {
    setTesting(true);
    setMsg(null);
    try {
      const c = await settingsApi.getLLM();
      if (c.status === 'connected') {
        setMsg({ text: 'LLM API 连接成功', ok: true });
      } else {
        setMsg({ text: 'LLM API 无法连接', ok: false });
      }
      setConfig(c);
    } catch {
      setMsg({ text: '测试失败', ok: false });
    }
    setTesting(false);
  };

  if (!config) return <div className="text-gray-400">加载中...</div>;

  return (
    <div className="space-y-6">
      {/* Status Banner */}
      <div className={`flex items-center gap-3 p-4 rounded-xl border ${
        config.status === 'connected'
          ? 'bg-green-50 border-green-200 text-green-800'
          : 'bg-amber-50 border-amber-200 text-amber-800'
      }`}>
        {config.status === 'connected'
          ? <CheckCircle2 className="w-5 h-5 text-green-500" />
          : <XCircle className="w-5 h-5 text-amber-500" />
        }
        <span className="font-medium">
          LLM API 状态: {config.status === 'connected' ? '已连接' : '未连接'}
        </span>
        <button
          onClick={handleTest}
          disabled={testing}
          className="ml-auto text-sm px-3 py-1 rounded-md border border-current opacity-80 hover:opacity-100"
        >
          {testing ? '测试中...' : '测试连接'}
        </button>
      </div>

      {/* API URL */}
      <Card title="API 地址" desc="OpenAI 兼容 API 端点（如 Ollama, vLLM, OpenAI, DeepSeek 等）">
        <input
          type="url"
          value={form.api_url}
          onChange={e => setForm({ ...form, api_url: e.target.value })}
          placeholder="http://localhost:11434/v1"
          className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
        />
        <p className="mt-1 text-xs text-gray-400">
          支持: Ollama (http://localhost:11434/v1), OpenAI (https://api.openai.com/v1), DeepSeek (https://api.deepseek.com/v1) 等
        </p>
      </Card>

      {/* API Key */}
      <Card title="API Key" desc="如果你的 LLM 提供商需要 API Key（如 OpenAI / DeepSeek），请在此配置">
        <div className="relative">
          <input
            type={showKey ? 'text' : 'password'}
            value={keyEdited ? form.api_key : (config.has_api_key ? config.api_key_masked : '')}
            onChange={e => { setForm({ ...form, api_key: e.target.value }); setKeyEdited(true); }}
            onFocus={() => { if (!keyEdited) { setForm({ ...form, api_key: '' }); setKeyEdited(true); } }}
            placeholder={config.has_api_key ? '已配置 (点击修改)' : '留空表示无需认证 (如 Ollama)'}
            className="w-full px-4 py-2.5 pr-20 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent font-mono"
          />
          <button
            type="button"
            onClick={() => setShowKey(!showKey)}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600"
          >
            {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
        {keyEdited && (
          <p className="mt-1 text-xs text-blue-500">Key 已修改，保存后生效</p>
        )}
      </Card>

      {/* Chat Model */}
      <Card title="对话模型" desc="用于标签建议、知识提取、RAG 对话的语言模型">
        <input
          type="text"
          value={form.model}
          onChange={e => setForm({ ...form, model: e.target.value })}
          placeholder="qwen2.5"
          className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent font-mono"
        />
        <p className="mt-1 text-xs text-gray-400">
          Ollama 模型名 (如 qwen2.5, llama3.1) 或 API 模型 ID (如 gpt-4o, deepseek-chat)
        </p>
      </Card>

      {/* Embedding Model + Dim */}
      <Card title="向量嵌入模型" desc="用于语义搜索的 Embedding 模型">
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2">
            <label className="block text-xs text-gray-500 mb-1">模型名称</label>
            <input
              type="text"
              value={form.embedding_model}
              onChange={e => setForm({ ...form, embedding_model: e.target.value })}
              placeholder="bge-m3"
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent font-mono"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">向量维度</label>
            <input
              type="number"
              min={128}
              max={4096}
              value={form.embedding_dim}
              onChange={e => setForm({ ...form, embedding_dim: parseInt(e.target.value) || 1024 })}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent font-mono text-center"
            />
          </div>
        </div>
        <p className="mt-1 text-xs text-gray-400">
          常见: bge-m3 (1024), text-embedding-3-small (1536), nomic-embed-text (768)
        </p>
      </Card>

      {/* Save */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
        >
          <Save className="w-4 h-4" /> {saving ? '保存中...' : '保存配置'}
        </button>
        {msg && (
          <span className={`text-sm font-medium ${msg.ok ? 'text-green-600' : 'text-red-500'}`}>
            {msg.ok ? <CheckCircle2 className="w-4 h-4 inline mr-1" /> : <XCircle className="w-4 h-4 inline mr-1" />}
            {msg.text}
          </span>
        )}
      </div>
    </div>
  );
}

/* ===== Apple 同步 ===== */

function SyncTab() {
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

  if (!syncConfig) return <div className="text-gray-400">加载中...</div>;

  return (
    <div className="space-y-6">
      <Card title="同步开关">
        <div className="space-y-4">
          <Toggle label="启用 Apple 同步" checked={syncConfig.enabled}
            onChange={v => setSyncConfig({ ...syncConfig, enabled: v })} />
          <Toggle label="自动定时同步" checked={syncConfig.auto_sync}
            onChange={v => setSyncConfig({ ...syncConfig, auto_sync: v })} />
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-700">同步间隔（分钟）</span>
            <input
              type="number" min={5} max={1440}
              value={syncConfig.interval_minutes}
              onChange={e => setSyncConfig({ ...syncConfig, interval_minutes: parseInt(e.target.value) || 30 })}
              className="w-24 px-3 py-1.5 border border-gray-200 rounded-lg text-sm text-right outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
        </div>
      </Card>

      <Card title="同步数据源">
        <div className="space-y-1">
          {[
            { key: 'notes', label: '备忘录 (Apple Notes)' },
            { key: 'reminders', label: '待办事项 (Apple Reminders)' },
            { key: 'calendar', label: '日历 (Apple Calendar)' },
          ].map(({ key, label }) => (
            <Toggle key={key} label={label} checked={syncConfig.sources[key] !== false}
              onChange={v => setSyncConfig({ ...syncConfig, sources: { ...syncConfig.sources, [key]: v } })} />
          ))}
        </div>
      </Card>

      <div className="flex items-center gap-3 pt-2">
        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
          <Save className="w-4 h-4" /> {saving ? '保存中...' : '保存配置'}
        </button>
        {message && <span className={`text-sm ${message.includes('失败') ? 'text-red-500' : 'text-green-500'}`}>{message}</span>}
      </div>
    </div>
  );
}

/* ===== 路径配置 ===== */

function PathsTab() {
  const [paths, setPaths] = useState({ obsidian_vault_path: '', data_dir: '' });
  const [resolved, setResolved] = useState({ resolved_vault_path: '', resolved_data_dir: '' });
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    settingsApi.getPaths().then(p => {
      setPaths({ obsidian_vault_path: p.obsidian_vault_path, data_dir: p.data_dir });
      setResolved({ resolved_vault_path: p.resolved_vault_path, resolved_data_dir: p.resolved_data_dir });
    }).catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMsg('');
    try {
      await settingsApi.updatePaths(paths);
      setMsg('路径配置已保存（重启后生效）');
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : '保存失败');
    }
    setSaving(false);
  };

  return (
    <div className="space-y-6">
      <Card title="Obsidian Vault 路径" desc="Markdown 笔记存储目录">
        <input type="text" value={paths.obsidian_vault_path}
          onChange={e => setPaths({ ...paths, obsidian_vault_path: e.target.value })}
          className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-400 font-mono" />
        <p className="mt-1 text-xs text-gray-400">解析后: {resolved.resolved_vault_path}</p>
      </Card>

      <Card title="数据目录" desc="SQLite 数据库和上传文件存储位置">
        <input type="text" value={paths.data_dir}
          onChange={e => setPaths({ ...paths, data_dir: e.target.value })}
          className="w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-400 font-mono" />
        <p className="mt-1 text-xs text-gray-400">解析后: {resolved.resolved_data_dir}</p>
      </Card>

      <div className="flex items-center gap-3 pt-2">
        <button onClick={handleSave} disabled={saving}
          className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium">
          <Save className="w-4 h-4" /> {saving ? '保存中...' : '保存配置'}
        </button>
        {msg && <span className="text-sm text-green-500">{msg}</span>}
      </div>
    </div>
  );
}

/* ===== 系统信息 ===== */

function SystemTab() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setInfo(await settingsApi.getSystemInfo()); } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!info) return <div className="text-gray-400">加载中...</div>;

  const svc = info.services;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-gray-800">服务状态</h2>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> 刷新
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatusCard label="LLM API" status={svc.llm.status === 'online'} detail={svc.llm.url} icon={Cpu} />
        <StatusCard label="Milvus 向量库"
          status={(svc.milvus as Record<string, unknown>)?.status === 'ok'}
          detail={`${info.data.milvus_vectors} 条向量`} icon={Database} />
        <StatusCard label="Neo4j 图数据库"
          status={(svc.neo4j as Record<string, unknown>)?.available === true}
          detail={`${info.data.neo4j_nodes} 个节点`} icon={Brain} />
      </div>

      <Card title="数据统计">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <Stat label="知识实体" value={info.data.entities} />
          <Stat label="待审核" value={info.data.pending_reviews} />
          <Stat label="对话数" value={info.data.conversations} />
          <Stat label="向量数" value={info.data.milvus_vectors} />
        </div>
      </Card>

      <Card title="版本信息">
        <div className="space-y-2 text-sm text-gray-600">
          <div className="flex justify-between"><span>版本</span><span className="font-mono">{info.version}</span></div>
          <div className="flex justify-between"><span>阶段</span><span>{info.phase}</span></div>
          <div className="flex justify-between"><span>认证模式</span><span>{info.auth_mode}</span></div>
          <div className="flex justify-between"><span>向量库模式</span><span className="font-mono">{info.vector_db_mode}</span></div>
        </div>
      </Card>
    </div>
  );
}

/* ===== Shared Components ===== */

function Card({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
      {desc && <p className="text-xs text-gray-400 mt-0.5 mb-3">{desc}</p>}
      {!desc && <div className="mt-3" />}
      {children}
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between py-2 cursor-pointer">
      <span className="text-sm text-gray-700">{label}</span>
      <div className="relative">
        <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} className="sr-only" />
        <div className={`w-10 h-5 rounded-full transition-colors ${checked ? 'bg-blue-600' : 'bg-gray-300'}`} onClick={() => onChange(!checked)}>
          <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${checked ? 'translate-x-5' : 'translate-x-0.5'}`} />
        </div>
      </div>
    </label>
  );
}

function StatusCard({ label, status, detail, icon: Icon }: {
  label: string; status: boolean; detail: string;
  icon: React.FC<{ className?: string }>;
}) {
  return (
    <div className={`rounded-xl border p-4 ${status ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4" />
        <span className="text-sm font-medium text-gray-800">{label}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full ${status ? 'bg-green-500' : 'bg-gray-400'}`} />
        <span className="text-xs text-gray-500">{status ? '在线' : '离线'}</span>
      </div>
      <p className="text-xs text-gray-400 mt-1 truncate">{detail}</p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-gray-50">
      <span className="text-gray-500">{label}</span>
      <span className="font-semibold text-gray-800">{value}</span>
    </div>
  );
}
