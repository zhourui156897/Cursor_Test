import { useEffect, useState, useCallback } from 'react';
import { syncApi, type SyncStatus, type SyncResult } from '../api/client';
import { Upload, RefreshCw, Cloud, CheckCircle, XCircle, Loader2, Plus, ArrowUpDown } from 'lucide-react';

const SOURCE_LABELS: Record<string, string> = {
  notes: '备忘录',
  reminders: '待办事项',
  calendar: '日历',
};

const LIMIT_OPTIONS = [5, 10, 20, 50, 100, 200];

export default function Ingest() {
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncing, setSyncing] = useState<Record<string, boolean>>({});
  const [syncResults, setSyncResults] = useState<Record<string, SyncResult | null>>({});
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string>('');
  const [dragOver, setDragOver] = useState(false);
  const [syncLimit, setSyncLimit] = useState(20);
  const [syncOrder, setSyncOrder] = useState<'newest' | 'oldest'>('newest');
  const [showSyncScope, setShowSyncScope] = useState(false);
  const [noteFolders, setNoteFolders] = useState<string[]>([]);
  const [reminderLists, setReminderLists] = useState<string[]>([]);
  const [selectedNoteFolders, setSelectedNoteFolders] = useState<string[]>([]);
  const [selectedReminderLists, setSelectedReminderLists] = useState<string[]>([]);
  const [daysBack, setDaysBack] = useState(30);
  const [daysForward, setDaysForward] = useState(90);
  const [dueAfter, setDueAfter] = useState('');
  const [dueBefore, setDueBefore] = useState('');
  const [showCreate, setShowCreate] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<Record<string, string>>({});
  const [creating, setCreating] = useState(false);
  const [createMsg, setCreateMsg] = useState('');
  const [showDataFlow, setShowDataFlow] = useState(false);

  const reload = useCallback(() => {
    syncApi.getStatus().then(setSyncStatus).catch(() => {});
  }, []);

  useEffect(() => { reload(); return undefined; }, [reload]);

  useEffect(() => {
    if (showSyncScope && noteFolders.length === 0) syncApi.getNoteFolders().then(r => setNoteFolders(r.folders || [])).catch(() => {});
    if (showSyncScope && reminderLists.length === 0) syncApi.getReminderLists().then(r => setReminderLists(r.lists || [])).catch(() => {});
  }, [showSyncScope, noteFolders.length, reminderLists.length]);

  const emptyResults = { total: 0, created: 0, updated: 0, skipped: 0 };

  const buildSyncOptions = (source: string) => {
    const opts: import('../api/client').SyncTriggerOptions = {};
    if (source === 'notes' && selectedNoteFolders.length > 0) opts.folder_whitelist = selectedNoteFolders;
    if (source === 'calendar') { opts.days_back = daysBack; opts.days_forward = daysForward; }
    if (source === 'reminders') {
      if (selectedReminderLists.length > 0) opts.list_names = selectedReminderLists;
      if (dueAfter) opts.due_after = dueAfter;
      if (dueBefore) opts.due_before = dueBefore;
    }
    return opts;
  };

  const handleSync = async (source: string) => {
    const apiSource = `apple_${source}`;
    setSyncing(s => ({ ...s, [source]: true }));
    setSyncResults(r => ({ ...r, [source]: null }));
    try {
      const options = buildSyncOptions(source);
      const result = await syncApi.trigger(apiSource, syncLimit, syncOrder, options);
      const res = result?.results ?? emptyResults;
      setSyncResults(r => ({ ...r, [source]: { message: result?.message ?? '', results: res } }));
      reload();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '同步失败';
      setSyncResults(r => ({ ...r, [source]: { message: msg, results: emptyResults } }));
    } finally {
      setSyncing(s => ({ ...s, [source]: false }));
    }
  };

  const handleSyncAll = async () => {
    setSyncing({ notes: true, reminders: true, calendar: true });
    try {
      await syncApi.triggerAll(syncLimit, syncOrder);
      reload();
    } catch {}
    setSyncing({});
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadResult('');
    const results: string[] = [];
    for (let i = 0; i < files.length; i++) {
      try {
        const res = await syncApi.upload(files[i]);
        results.push(`✅ ${files[i].name}: ${res.status === 'created' ? '已创建 → 进入审核队列' : res.status}`);
      } catch (e: unknown) {
        results.push(`❌ ${files[i].name}: ${e instanceof Error ? e.message : '上传失败'}`);
      }
    }
    setUploadResult(results.join('\n'));
    setUploading(false);
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleCreate = async (type: string) => {
    setCreating(true);
    setCreateMsg('');
    try {
      if (type === 'note') {
        await syncApi.createNote({
          title: createForm.title || '新备忘录',
          body: createForm.body ?? '',
          folder: createForm.folder ?? '',
        });
        setCreateMsg('✅ 备忘录已创建');
      } else if (type === 'reminder') {
        await syncApi.createReminder({
          title: createForm.title || '新提醒',
          body: createForm.body ?? '',
          list_name: createForm.list_name ?? '',
          due_date: createForm.due_date ?? '',
          priority: Number(createForm.priority) || 0,
        });
        setCreateMsg('✅ 提醒事项已创建');
      } else if (type === 'event') {
        const start = createForm.start_date || new Date().toISOString().slice(0, 19);
        const end = createForm.end_date || new Date(Date.now() + 3600000).toISOString().slice(0, 19);
        await syncApi.createEvent({
          title: createForm.title || '新日历事件',
          start_date: start,
          end_date: end,
          description: createForm.description || '',
          location: createForm.location || '',
          calendar: createForm.calendar || '',
        });
        setCreateMsg('✅ 日历事件已创建');
      }
      setCreateForm({});
    } catch (e: unknown) {
      setCreateMsg(`❌ ${e instanceof Error ? e.message : '创建失败'}`);
    }
    setCreating(false);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">数据摄入</h1>

      {/* File Upload Zone */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Upload className="w-5 h-5 text-blue-500" /> 文件上传
        </h2>
        <div
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
            dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => {
            const input = document.createElement('input');
            input.type = 'file';
            input.multiple = true;
            input.onchange = () => handleFiles(input.files);
            input.click();
          }}
        >
          {uploading ? (
            <div className="flex items-center justify-center gap-2 text-blue-500">
              <Loader2 className="w-5 h-5 animate-spin" /> 处理中...
            </div>
          ) : (
            <>
              <Upload className="w-8 h-8 text-gray-300 mx-auto mb-2" />
              <p className="text-sm text-gray-500">拖拽文件到此处，或点击选择文件</p>
              <p className="text-xs text-gray-400 mt-1">支持 Word、PDF、Excel、文本、图片、音频等格式</p>
            </>
          )}
        </div>
        {uploadResult && (
          <pre className="mt-3 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 whitespace-pre-wrap">{uploadResult}</pre>
        )}
      </div>

      {/* Apple Sync Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
            <Cloud className="w-5 h-5 text-green-500" /> Apple 数据同步
          </h2>
          <button onClick={handleSyncAll} disabled={Object.values(syncing).some(Boolean)}
            className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
            <RefreshCw className="w-4 h-4" /> 全部同步
          </button>
        </div>

        {/* 数据流说明（可折叠） */}
        <div className="mb-4">
          <button type="button" onClick={() => setShowDataFlow(!showDataFlow)}
            className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1">
            {showDataFlow ? '▼' : '▶'} 日历/待办如何进入数据库？
          </button>
          {showDataFlow && (
            <div className="mt-2 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 space-y-1">
              <p><strong>同步</strong>：从 Mac 备忘录/待办/日历读取 → 每条写入数据库实体 + Obsidian 笔记 → LLM 建议标签 → 审核队列。审核通过后标签回写 Obsidian。</p>
              <p><strong>Agent 创建</strong>：在系统 App 里真正创建；若开启「记入知识库」，会同时在本系统建一条实体便于检索。</p>
            </div>
          )}
        </div>

        {/* Sync Options */}
        <div className="mb-4 flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2 text-sm">
            <ArrowUpDown className="w-4 h-4 text-gray-400" />
            <span className="text-gray-500">数量:</span>
            <select value={syncLimit} onChange={e => setSyncLimit(Number(e.target.value))}
              className="border rounded px-2 py-1 text-sm">
              {LIMIT_OPTIONS.map(n => <option key={n} value={n}>{n} 条</option>)}
            </select>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-gray-500">排序:</span>
            <select value={syncOrder} onChange={e => setSyncOrder(e.target.value as 'newest' | 'oldest')}
              className="border rounded px-2 py-1 text-sm">
              <option value="newest">由新到旧</option>
              <option value="oldest">由旧到新</option>
            </select>
          </div>
          <button type="button" onClick={() => setShowSyncScope(!showSyncScope)}
            className="text-sm text-blue-600 hover:underline">
            {showSyncScope ? '收起' : '展开'} 同步范围（可选）
          </button>
          {syncStatus && (
            <span className="text-xs text-gray-400">
              自动同步: {syncStatus.config.auto_sync ? '开启' : '关闭'} · 间隔: {syncStatus.config.interval_minutes}分钟
            </span>
          )}
        </div>

        {/* 同步范围：备忘录文件夹、日历时间、待办列表与截止 */}
        {showSyncScope && (
          <div className="mb-4 p-4 border border-gray-200 rounded-xl bg-gray-50/50">
            <p className="text-sm font-medium text-gray-700 mb-3">首次或选择性导入（不选则同步全部）</p>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-gray-500 mb-2">备忘录 · 选择文件夹</p>
                <div className="flex flex-wrap gap-2 max-h-24 overflow-auto">
                  {noteFolders.map(f => (
                    <label key={f} className="flex items-center gap-1 cursor-pointer">
                      <input type="checkbox" checked={selectedNoteFolders.includes(f)}
                        onChange={e => setSelectedNoteFolders(prev => e.target.checked ? [...prev, f] : prev.filter(x => x !== f))} />
                      <span>{f}</span>
                    </label>
                  ))}
                  {noteFolders.length === 0 && <span className="text-gray-400">加载中…</span>}
                </div>
              </div>
              <div>
                <p className="text-gray-500 mb-2">日历 · 时间范围（天）</p>
                <div className="flex gap-2 items-center">
                  <span>过去</span>
                  <input type="number" min={0} max={365} value={daysBack} onChange={e => setDaysBack(Number(e.target.value) || 0)}
                    className="w-16 border rounded px-2 py-1" />
                  <span>天 → 未来</span>
                  <input type="number" min={0} max={365} value={daysForward} onChange={e => setDaysForward(Number(e.target.value) || 0)}
                    className="w-16 border rounded px-2 py-1" />
                  <span>天</span>
                </div>
              </div>
              <div>
                <p className="text-gray-500 mb-2">待办 · 选择列表</p>
                <div className="flex flex-wrap gap-2 max-h-24 overflow-auto mb-2">
                  {reminderLists.map(l => (
                    <label key={l} className="flex items-center gap-1 cursor-pointer">
                      <input type="checkbox" checked={selectedReminderLists.includes(l)}
                        onChange={e => setSelectedReminderLists(prev => e.target.checked ? [...prev, l] : prev.filter(x => x !== l))} />
                      <span>{l}</span>
                    </label>
                  ))}
                  {reminderLists.length === 0 && <span className="text-gray-400">加载中…</span>}
                </div>
                <p className="text-gray-500 text-xs mt-1">截止范围（可选）</p>
                <div className="flex gap-1 mt-1">
                  <input type="date" value={dueAfter} onChange={e => setDueAfter(e.target.value)} className="border rounded px-2 py-1 text-xs" placeholder="起" />
                  <input type="date" value={dueBefore} onChange={e => setDueBefore(e.target.value)} className="border rounded px-2 py-1 text-xs" placeholder="止" />
                </div>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-3 gap-4">
          {Object.entries(SOURCE_LABELS).map(([key, label]) => {
            const enabled = syncStatus?.config.sources[key] !== false;
            const status = syncStatus?.status[`apple_${key}`];
            const result = syncResults[key];
            const isRunning = syncing[key];

            return (
              <div key={key} className="border border-gray-100 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${enabled ? 'bg-green-400' : 'bg-gray-300'}`} />
                    <span className="font-medium text-gray-800">{label}</span>
                  </div>
                  <button onClick={() => handleSync(key)} disabled={isRunning || !enabled}
                    className="text-xs text-blue-500 hover:underline disabled:opacity-50 flex items-center gap-1">
                    {isRunning ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    同步
                  </button>
                </div>
                {status?.last_run && (
                  <p className="text-xs text-gray-400 mb-2">上次: {new Date(status.last_run).toLocaleString('zh-CN')}</p>
                )}
                {result && (
                  <div className="text-xs space-y-1">
                    {((result.results) || emptyResults).created > 0 && (
                      <p className="flex items-center gap-1 text-green-600">
                        <CheckCircle className="w-3 h-3" /> 新增 {(result.results || emptyResults).created} 条
                      </p>
                    )}
                    {((result.results) || emptyResults).updated > 0 && (
                      <p className="flex items-center gap-1 text-blue-600">
                        <RefreshCw className="w-3 h-3" /> 更新 {(result.results || emptyResults).updated} 条
                      </p>
                    )}
                    {((result.results) || emptyResults).skipped > 0 && (
                      <p className="text-gray-400">跳过 {(result.results || emptyResults).skipped} 条</p>
                    )}
                    {((result.results) || emptyResults).total === 0 && result.message && (
                      <p className="flex items-center gap-1 text-red-500">
                        <XCircle className="w-3 h-3" /> {result.message}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Create Apple Data */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
          <Plus className="w-5 h-5 text-purple-500" /> 新建 Apple 数据
        </h2>
        <div className="flex gap-2 mb-4">
          {(['note', 'reminder', 'event'] as const).map(t => (
            <button key={t} onClick={() => { setShowCreate(showCreate === t ? null : t); setCreateForm({}); setCreateMsg(''); }}
              className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${
                showCreate === t ? 'bg-purple-50 border-purple-300 text-purple-700' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
              }`}>
              {t === 'note' ? '📝 新备忘录' : t === 'reminder' ? '✅ 新提醒事项' : '📅 新日历事件'}
            </button>
          ))}
        </div>

        {showCreate === 'note' && (
          <div className="space-y-3 border-t pt-4">
            <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="标题"
              value={createForm.title || ''} onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))} />
            <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-24" placeholder="内容"
              value={createForm.body || ''} onChange={e => setCreateForm(f => ({ ...f, body: e.target.value }))} />
            <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="文件夹名 (可选)"
              value={createForm.folder || ''} onChange={e => setCreateForm(f => ({ ...f, folder: e.target.value }))} />
            <button onClick={() => handleCreate('note')} disabled={creating || !createForm.title}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700 disabled:opacity-50">
              {creating ? '创建中...' : '创建备忘录'}
            </button>
          </div>
        )}

        {showCreate === 'reminder' && (
          <div className="space-y-3 border-t pt-4">
            <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="提醒标题"
              value={createForm.title || ''} onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))} />
            <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="备注 (可选)"
              value={createForm.body || ''} onChange={e => setCreateForm(f => ({ ...f, body: e.target.value }))} />
            <div className="flex gap-2">
              <input className="flex-1 border rounded-lg px-3 py-2 text-sm" type="datetime-local" placeholder="截止时间"
                value={createForm.due_date || ''} onChange={e => setCreateForm(f => ({ ...f, due_date: e.target.value }))} />
              <select className="border rounded-lg px-3 py-2 text-sm" value={createForm.priority || '0'}
                onChange={e => setCreateForm(f => ({ ...f, priority: e.target.value }))}>
                <option value="0">无优先级</option>
                <option value="1">高</option>
                <option value="5">中</option>
                <option value="9">低</option>
              </select>
            </div>
            <button onClick={() => handleCreate('reminder')} disabled={creating || !createForm.title}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700 disabled:opacity-50">
              {creating ? '创建中...' : '创建提醒事项'}
            </button>
          </div>
        )}

        {showCreate === 'event' && (
          <div className="space-y-3 border-t pt-4">
            <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="事件标题"
              value={createForm.title || ''} onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))} />
            <div className="flex gap-2">
              <div className="flex-1">
                <label className="text-xs text-gray-500">开始时间</label>
                <input className="w-full border rounded-lg px-3 py-2 text-sm" type="datetime-local"
                  value={createForm.start_date || ''} onChange={e => setCreateForm(f => ({ ...f, start_date: e.target.value }))} />
              </div>
              <div className="flex-1">
                <label className="text-xs text-gray-500">结束时间</label>
                <input className="w-full border rounded-lg px-3 py-2 text-sm" type="datetime-local"
                  value={createForm.end_date || ''} onChange={e => setCreateForm(f => ({ ...f, end_date: e.target.value }))} />
              </div>
            </div>
            <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="地点 (可选)"
              value={createForm.location || ''} onChange={e => setCreateForm(f => ({ ...f, location: e.target.value }))} />
            <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-16" placeholder="描述 (可选)"
              value={createForm.description || ''} onChange={e => setCreateForm(f => ({ ...f, description: e.target.value }))} />
            <button onClick={() => handleCreate('event')} disabled={creating || !createForm.title}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700 disabled:opacity-50">
              {creating ? '创建中...' : '创建日历事件'}
            </button>
          </div>
        )}

        {createMsg && <p className="mt-3 text-sm">{createMsg}</p>}
      </div>
    </div>
  );
}
