import { useEffect, useState, useCallback } from 'react';
import { reviewApi, tagApi, type ReviewItem, type ReviewStats } from '../api/client';
import { CheckCircle, XCircle, ChevronDown, ChevronUp, Tag, Filter, Edit3 } from 'lucide-react';

const SOURCE_LABELS: Record<string, string> = {
  upload: '上传', apple_notes: '备忘录', apple_reminders: '待办',
  apple_calendar: '日历', obsidian: 'Obsidian',
};

const STATUS_TABS = [
  { key: 'all', label: '全部' },
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已通过' },
  { key: 'modified', label: '已修改' },
  { key: 'rejected', label: '已拒绝' },
];

export default function ReviewQueue() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState('pending');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [processing, setProcessing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [manualTags, setManualTags] = useState<{ folder_tags: string[]; content_tags: string[]; status: Record<string, string> }>({
    folder_tags: [], content_tags: [], status: {},
  });
  const [availableTags, setAvailableTags] = useState<{ folder: string[]; content: string[] }>({ folder: [], content: [] });
  const [newTag, setNewTag] = useState('');

  const reload = useCallback(() => {
    reviewApi.list(filter).then(r => { setItems(r.items); setTotal(r.total); }).catch(() => {});
    reviewApi.getStats().then(setStats).catch(() => {});
  }, [filter]);

  useEffect(() => { reload(); return undefined; }, [reload]);

  useEffect(() => {
    tagApi.listTree().then(tree => {
      const paths: string[] = [];
      const walk = (nodes: { path?: string; name?: string; children?: unknown[] }[]) => {
        for (const n of nodes) {
          const p = (n as Record<string, unknown>).path as string | undefined;
          if (p) paths.push(p);
          else if (n.name) paths.push(n.name);
          if (Array.isArray((n as Record<string, unknown>).children)) walk((n as Record<string, unknown>).children as typeof nodes);
        }
      };
      walk(tree as unknown as { path?: string; name?: string; children?: unknown[] }[]);
      setAvailableTags(prev => ({ ...prev, folder: paths }));
    }).catch(() => {});
    tagApi.listContent().then(tags => {
      setAvailableTags(prev => ({ ...prev, content: tags.map(t => t.name) }));
    }).catch(() => {});
  }, []);

  const handleApprove = async (id: string) => {
    setProcessing(true);
    try { await reviewApi.approve(id); reload(); } catch {}
    setProcessing(false);
  };

  const handleReject = async (id: string) => {
    setProcessing(true);
    try { await reviewApi.reject(id); reload(); } catch {}
    setProcessing(false);
  };

  const handleManualTag = async (id: string) => {
    setProcessing(true);
    try { await reviewApi.manualTag(id, manualTags); setEditingId(null); reload(); } catch {}
    setProcessing(false);
  };

  const handleBatchApprove = async () => {
    if (selected.size === 0) return;
    setProcessing(true);
    try { await reviewApi.batchApprove([...selected]); setSelected(new Set()); reload(); } catch {}
    setProcessing(false);
  };

  const toggleSelect = (id: string) => {
    setSelected(s => { const next = new Set(s); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  };
  const selectAll = () => {
    setSelected(selected.size === items.length ? new Set() : new Set(items.map(i => i.id)));
  };

  const startEditing = (item: ReviewItem) => {
    setEditingId(item.id);
    setManualTags({
      folder_tags: item.suggested_folder_tags || [],
      content_tags: item.suggested_content_tags || [],
      status: item.suggested_status || {},
    });
  };

  const statusColor = (s: string) =>
    s === 'pending' ? 'bg-amber-100 text-amber-700' :
    s === 'approved' ? 'bg-green-100 text-green-700' :
    s === 'modified' ? 'bg-blue-100 text-blue-700' :
    s === 'rejected' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700';

  const pendingItems = items.filter(i => i.status === 'pending');

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">审核管理</h1>
          {stats && (
            <p className="text-sm text-gray-500 mt-1">
              共 {stats.total} 条 · 待审核 {stats.pending || 0} · 已通过 {(stats.approved || 0) + (stats.modified || 0)} · 已拒绝 {stats.rejected || 0}
            </p>
          )}
        </div>
        {pendingItems.length > 0 && filter === 'pending' && (
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer">
              <input type="checkbox" checked={selected.size === pendingItems.length && pendingItems.length > 0} onChange={selectAll} className="rounded" />
              全选
            </label>
            <button onClick={handleBatchApprove} disabled={selected.size === 0 || processing}
              className="flex items-center gap-1 px-4 py-2 bg-green-600 text-white rounded-lg text-sm hover:bg-green-700 disabled:opacity-50">
              <CheckCircle className="w-4 h-4" /> 批量通过 ({selected.size})
            </button>
          </div>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit">
        {STATUS_TABS.map(tab => (
          <button key={tab.key} onClick={() => { setFilter(tab.key); setSelected(new Set()); }}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${filter === tab.key ? 'bg-white shadow text-gray-900 font-medium' : 'text-gray-500 hover:text-gray-700'}`}>
            <Filter className="w-3 h-3 inline mr-1" />
            {tab.label}
            {stats && tab.key !== 'all' && (stats as Record<string, number>)[tab.key] > 0 && (
              <span className="ml-1 text-xs bg-gray-200 rounded-full px-1.5">{(stats as Record<string, number>)[tab.key]}</span>
            )}
          </button>
        ))}
      </div>

      {/* List */}
      {items.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <CheckCircle className="w-10 h-10 text-green-300 mx-auto mb-3" />
          <p className="text-gray-500">{filter === 'pending' ? '暂无待审核内容' : '暂无数据'}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map(item => {
            const isExpanded = expanded === item.id;
            const isEditing = editingId === item.id;
            return (
              <div key={item.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="flex items-center px-5 py-4">
                  {item.status === 'pending' && (
                    <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleSelect(item.id)} className="mr-4 rounded" />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-800 truncate">{item.entity_title || '无标题'}</span>
                      <span className="text-xs px-2 py-0.5 bg-gray-100 text-gray-500 rounded">
                        {SOURCE_LABELS[item.entity_source || ''] || item.entity_source}
                      </span>
                      <span className={`text-xs px-2 py-0.5 rounded ${statusColor(item.status)}`}>
                        {item.status === 'pending' ? '待审核' : item.status === 'approved' ? '已通过' : item.status === 'modified' ? '已修改' : '已拒绝'}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {item.suggested_folder_tags?.map(t => (
                        <span key={t} className="text-xs px-2 py-0.5 bg-blue-50 text-blue-700 rounded">📁 {t}</span>
                      ))}
                      {item.suggested_content_tags?.map(t => (
                        <span key={t} className="text-xs px-2 py-0.5 bg-green-50 text-green-700 rounded">#{t}</span>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4 shrink-0">
                    {item.status === 'pending' && (
                      <>
                        <button onClick={() => handleApprove(item.id)} disabled={processing}
                          className="p-2 text-green-500 hover:bg-green-50 rounded-lg" title="通过">
                          <CheckCircle className="w-5 h-5" />
                        </button>
                        <button onClick={() => startEditing(item)} disabled={processing}
                          className="p-2 text-blue-500 hover:bg-blue-50 rounded-lg" title="手动配置标签">
                          <Edit3 className="w-5 h-5" />
                        </button>
                        <button onClick={() => handleReject(item.id)} disabled={processing}
                          className="p-2 text-red-400 hover:bg-red-50 rounded-lg" title="拒绝">
                          <XCircle className="w-5 h-5" />
                        </button>
                      </>
                    )}
                    <button onClick={() => setExpanded(isExpanded ? null : item.id)}
                      className="p-2 text-gray-400 hover:bg-gray-50 rounded-lg">
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Manual tag editor */}
                {isEditing && (
                  <div className="border-t border-blue-100 px-5 py-4 bg-blue-50/50">
                    <p className="text-sm font-medium text-blue-800 mb-3 flex items-center gap-1"><Tag className="w-4 h-4" /> 手动配置标签</p>

                    <div className="mb-3">
                      <label className="text-xs text-gray-500 mb-1 block">文件夹标签</label>
                      <div className="flex flex-wrap gap-1 mb-1">
                        {manualTags.folder_tags.map(t => (
                          <span key={t} className="text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded flex items-center gap-1">
                            📁 {t}
                            <button onClick={() => setManualTags(prev => ({ ...prev, folder_tags: prev.folder_tags.filter(x => x !== t) }))}
                              className="text-blue-400 hover:text-blue-600">&times;</button>
                          </span>
                        ))}
                      </div>
                      <select className="text-sm border rounded px-2 py-1 w-full" value=""
                        onChange={e => { if (e.target.value && !manualTags.folder_tags.includes(e.target.value)) setManualTags(prev => ({ ...prev, folder_tags: [...prev.folder_tags, e.target.value] })); }}>
                        <option value="">选择文件夹标签...</option>
                        {availableTags.folder.map(p => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </div>

                    <div className="mb-3">
                      <label className="text-xs text-gray-500 mb-1 block">内容标签</label>
                      <div className="flex flex-wrap gap-1 mb-1">
                        {manualTags.content_tags.map(t => (
                          <span key={t} className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded flex items-center gap-1">
                            #{t}
                            <button onClick={() => setManualTags(prev => ({ ...prev, content_tags: prev.content_tags.filter(x => x !== t) }))}
                              className="text-green-400 hover:text-green-600">&times;</button>
                          </span>
                        ))}
                      </div>
                      <div className="flex gap-1">
                        <input className="text-sm border rounded px-2 py-1 flex-1" placeholder="输入标签或选择"
                          value={newTag} onChange={e => setNewTag(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter' && newTag.trim()) { setManualTags(prev => ({ ...prev, content_tags: [...prev.content_tags, newTag.trim()] })); setNewTag(''); }}} />
                        {availableTags.content.length > 0 && (
                          <select className="text-sm border rounded px-2 py-1" value=""
                            onChange={e => { if (e.target.value && !manualTags.content_tags.includes(e.target.value)) setManualTags(prev => ({ ...prev, content_tags: [...prev.content_tags, e.target.value] })); }}>
                            <option value="">已有标签</option>
                            {availableTags.content.map(t => <option key={t} value={t}>{t}</option>)}
                          </select>
                        )}
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <button onClick={() => handleManualTag(item.id)} disabled={processing}
                        className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50">
                        应用标签
                      </button>
                      <button onClick={() => setEditingId(null)} className="px-4 py-1.5 bg-gray-200 text-gray-600 rounded text-sm hover:bg-gray-300">
                        取消
                      </button>
                    </div>
                  </div>
                )}

                {/* Content preview */}
                {isExpanded && (
                  <div className="border-t border-gray-100 px-5 py-4 bg-gray-50">
                    <p className="text-xs text-gray-500 mb-2">内容预览:</p>
                    <div className="text-sm text-gray-700 whitespace-pre-wrap max-h-48 overflow-auto bg-white p-3 rounded-lg border border-gray-100">
                      {item.entity_content?.slice(0, 1000) || '(无内容)'}
                    </div>
                    {item.reviewer_action && (
                      <div className="mt-3 text-xs text-gray-500">
                        审核结果: <code className="bg-gray-200 px-1 rounded">{JSON.stringify(item.reviewer_action)}</code>
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
