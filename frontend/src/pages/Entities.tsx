import { useEffect, useState } from 'react';
import { entityApi, type Entity } from '../api/client';
import { Plus, FileText, Trash2 } from 'lucide-react';

export default function Entities() {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ title: '', content: '' });

  const reload = () => { entityApi.list().then(setEntities); };
  useEffect(reload, []);

  const handleAdd = async () => {
    if (!form.title.trim()) return;
    await entityApi.create({ title: form.title, content: form.content, source: 'upload' });
    setForm({ title: '', content: '' });
    setShowAdd(false);
    reload();
  };

  const SOURCE_LABELS: Record<string, string> = {
    upload: '上传',
    apple_notes: '备忘录',
    apple_reminders: '待办',
    apple_calendar: '日历',
    obsidian: 'Obsidian',
  };

  const STATUS_COLORS: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    reviewed: 'bg-green-100 text-green-700',
    auto: 'bg-blue-100 text-blue-700',
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">实体管理</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> 新建实体
        </button>
      </div>

      {showAdd && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6 space-y-3">
          <input
            placeholder="标题"
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none focus:ring-1 focus:ring-blue-400"
          />
          <textarea
            placeholder="内容（可选）"
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            rows={4}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none focus:ring-1 focus:ring-blue-400 resize-none"
          />
          <button onClick={handleAdd} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            创建
          </button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
        {entities.length === 0 && (
          <div className="p-8 text-center text-gray-400 text-sm">暂无实体数据</div>
        )}
        {entities.map((e) => (
          <div key={e.id} className="flex items-center justify-between px-5 py-3 hover:bg-gray-50 group">
            <div className="flex items-center gap-3">
              <FileText className="w-4 h-4 text-gray-400" />
              <div>
                <div className="text-sm font-medium text-gray-800">{e.title}</div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs text-gray-400">{SOURCE_LABELS[e.source] || e.source}</span>
                  <span className="text-xs text-gray-300">v{e.current_version}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[e.review_status] || 'bg-gray-100 text-gray-500'}`}>
                    {e.review_status === 'pending' ? '待审核' : e.review_status === 'reviewed' ? '已审核' : e.review_status}
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-400">{e.updated_at}</span>
              <button
                onClick={() => { if (confirm('确定删除？')) entityApi.delete(e.id).then(reload); }}
                className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
