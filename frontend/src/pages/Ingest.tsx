import { useEffect, useState, useCallback } from 'react';
import { syncApi, type SyncStatus, type SyncResult } from '../api/client';
import { Upload, RefreshCw, Cloud, CheckCircle, XCircle, Loader2 } from 'lucide-react';

const SOURCE_LABELS: Record<string, string> = {
  notes: '备忘录',
  reminders: '待办事项',
  calendar: '日历',
};

export default function Ingest() {
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [syncing, setSyncing] = useState<Record<string, boolean>>({});
  const [syncResults, setSyncResults] = useState<Record<string, SyncResult | null>>({});
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string>('');
  const [dragOver, setDragOver] = useState(false);

  const reload = useCallback(() => {
    syncApi.getStatus().then(setSyncStatus).catch(() => {});
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const handleSync = async (source: string) => {
    const apiSource = `apple_${source}`;
    setSyncing(s => ({ ...s, [source]: true }));
    setSyncResults(r => ({ ...r, [source]: null }));
    try {
      const result = await syncApi.trigger(apiSource);
      setSyncResults(r => ({ ...r, [source]: result }));
      reload();
    } catch (e: unknown) {
      setSyncResults(r => ({ ...r, [source]: { message: e instanceof Error ? e.message : '同步失败', results: { total: 0, created: 0, updated: 0, skipped: 0 } } }));
    } finally {
      setSyncing(s => ({ ...s, [source]: false }));
    }
  };

  const handleSyncAll = async () => {
    setSyncing({ notes: true, reminders: true, calendar: true });
    try {
      await syncApi.triggerAll();
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
        results.push(`${files[i].name}: ${res.status === 'created' ? '已创建' : res.status}`);
      } catch (e: unknown) {
        results.push(`${files[i].name}: ${e instanceof Error ? e.message : '失败'}`);
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
              <p className="text-xs text-gray-400 mt-1">支持文本、PDF、图片、音频、视频等格式</p>
            </>
          )}
        </div>
        {uploadResult && (
          <pre className="mt-3 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 whitespace-pre-wrap">{uploadResult}</pre>
        )}
      </div>

      {/* Apple Sync Section */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
            <Cloud className="w-5 h-5 text-green-500" /> Apple 数据同步
          </h2>
          <button
            onClick={handleSyncAll}
            disabled={Object.values(syncing).some(Boolean)}
            className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className="w-4 h-4" /> 全部同步
          </button>
        </div>

        {syncStatus && (
          <div className="mb-4 flex items-center gap-4 text-sm text-gray-500">
            <span>自动同步: {syncStatus.config.auto_sync ? '开启' : '关闭'}</span>
            <span>间隔: {syncStatus.config.interval_minutes}分钟</span>
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
                  <button
                    onClick={() => handleSync(key)}
                    disabled={isRunning || !enabled}
                    className="text-xs text-blue-500 hover:underline disabled:opacity-50 flex items-center gap-1"
                  >
                    {isRunning ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                    同步
                  </button>
                </div>

                {status?.last_run && (
                  <p className="text-xs text-gray-400 mb-2">上次: {new Date(status.last_run).toLocaleString('zh-CN')}</p>
                )}

                {result && (
                  <div className="text-xs space-y-1">
                    {result.results.created > 0 && (
                      <p className="flex items-center gap-1 text-green-600">
                        <CheckCircle className="w-3 h-3" /> 新增 {result.results.created} 条
                      </p>
                    )}
                    {result.results.updated > 0 && (
                      <p className="flex items-center gap-1 text-blue-600">
                        <RefreshCw className="w-3 h-3" /> 更新 {result.results.updated} 条
                      </p>
                    )}
                    {result.results.skipped > 0 && (
                      <p className="text-gray-400">跳过 {result.results.skipped} 条 (无变化)</p>
                    )}
                    {result.results.total === 0 && result.message && (
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
    </div>
  );
}
