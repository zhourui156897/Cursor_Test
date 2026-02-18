import { useEffect, useState, useCallback } from 'react';
import { reviewApi, type ReviewItem } from '../api/client';
import { CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';

const SOURCE_LABELS: Record<string, string> = {
  upload: '上传', apple_notes: '备忘录', apple_reminders: '待办',
  apple_calendar: '日历', obsidian: 'Obsidian',
};

export default function ReviewQueue() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [count, setCount] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [processing, setProcessing] = useState(false);

  const reload = useCallback(() => {
    reviewApi.listPending().then(setItems).catch(() => {});
    reviewApi.getCount().then(r => setCount(r.count)).catch(() => {});
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const handleApprove = async (id: string) => {
    setProcessing(true);
    try {
      await reviewApi.approve(id);
      reload();
    } catch {}
    setProcessing(false);
  };

  const handleReject = async (id: string) => {
    setProcessing(true);
    try {
      await reviewApi.reject(id);
      reload();
    } catch {}
    setProcessing(false);
  };

  const handleBatchApprove = async () => {
    if (selected.size === 0) return;
    setProcessing(true);
    try {
      await reviewApi.batchApprove([...selected]);
      setSelected(new Set());
      reload();
    } catch {}
    setProcessing(false);
  };

  const toggleSelect = (id: string) => {
    setSelected(s => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const selectAll = () => {
    if (selected.size === items.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(items.map(i => i.id)));
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">审核队列</h1>
          <p className="text-sm text-gray-500 mt-1">共 {count} 条待审核</p>
        </div>
        {items.length > 0 && (
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer">
              <input type="checkbox" checked={selected.size === items.length && items.length > 0} onChange={selectAll} className="rounded" />
              全选
            </label>
            <button
              onClick={handleBatchApprove}
              disabled={selected.size === 0 || processing}
              className="flex items-center gap-1 px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
            >
              <CheckCircle className="w-4 h-4" /> 批量通过 ({selected.size})
            </button>
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <CheckCircle className="w-10 h-10 text-green-300 mx-auto mb-3" />
          <p className="text-gray-500">所有内容已审核完毕</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => {
            const isExpanded = expanded === item.id;
            return (
              <div key={item.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="flex items-center px-5 py-4">
                  <input
                    type="checkbox"
                    checked={selected.has(item.id)}
                    onChange={() => toggleSelect(item.id)}
                    className="mr-4 rounded"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-800 truncate">{item.entity_title || '无标题'}</span>
                      <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded">
                        {SOURCE_LABELS[item.entity_source || ''] || item.entity_source}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {item.suggested_folder_tags?.map(t => (
                        <span key={t} className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded">📁 {t}</span>
                      ))}
                      {item.suggested_content_tags?.map(t => (
                        <span key={t} className="text-xs px-2 py-0.5 bg-green-50 text-green-700 rounded">#{t}</span>
                      ))}
                      {item.suggested_status && Object.entries(item.suggested_status).map(([k, v]) => (
                        <span key={k} className="text-xs px-2 py-0.5 bg-purple-50 text-purple-700 rounded">{k}: {v}</span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4 shrink-0">
                    <button
                      onClick={() => handleApprove(item.id)}
                      disabled={processing}
                      className="p-2 text-green-500 hover:bg-green-50 rounded-lg"
                      title="通过"
                    >
                      <CheckCircle className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => handleReject(item.id)}
                      disabled={processing}
                      className="p-2 text-red-400 hover:bg-red-50 rounded-lg"
                      title="拒绝"
                    >
                      <XCircle className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => setExpanded(isExpanded ? null : item.id)}
                      className="p-2 text-gray-400 hover:bg-gray-50 rounded-lg"
                    >
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="border-t border-gray-100 px-5 py-4 bg-gray-50">
                    <p className="text-xs text-gray-500 mb-2">内容预览:</p>
                    <div className="text-sm text-gray-700 whitespace-pre-wrap max-h-48 overflow-auto bg-white p-3 rounded-lg border border-gray-100">
                      {item.entity_content?.slice(0, 1000) || '(无内容)'}
                    </div>
                    {item.confidence_scores && (
                      <div className="mt-3">
                        <p className="text-xs text-gray-500 mb-1">置信度:</p>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(item.confidence_scores).map(([category, scores]) => {
                            if (typeof scores === 'object' && scores !== null) {
                              return Object.entries(scores as Record<string, number>).map(([tag, score]) => (
                                <span key={`${category}-${tag}`} className={`text-xs px-2 py-0.5 rounded ${
                                  score >= 0.8 ? 'bg-green-100 text-green-700' : score >= 0.5 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-50 text-red-600'
                                }`}>
                                  {tag}: {(score * 100).toFixed(0)}%
                                </span>
                              ));
                            }
                            return null;
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
