import { useEffect, useState } from 'react';
import { tagApi, type TagTree, type ContentTag, type StatusDimension } from '../api/client';
import { Plus, Trash2, ChevronRight, ChevronDown } from 'lucide-react';

export default function TagManager() {
  const [treeTags, setTreeTags] = useState<TagTree[]>([]);
  const [contentTags, setContentTags] = useState<ContentTag[]>([]);
  const [statusDims, setStatusDims] = useState<StatusDimension[]>([]);
  const [newTreeName, setNewTreeName] = useState('');
  const [newContentName, setNewContentName] = useState('');
  const [newContentColor, setNewContentColor] = useState('#4A90D9');
  const [newDimKey, setNewDimKey] = useState('');
  const [newDimOptions, setNewDimOptions] = useState('');
  const [selectedParent, setSelectedParent] = useState<string | undefined>();
  const [error, setError] = useState('');

  const reload = () => {
    tagApi.listTree().then(setTreeTags).catch(() => {});
    tagApi.listContent().then(setContentTags).catch(() => {});
    tagApi.listStatus().then(setStatusDims).catch(() => {});
  };

  useEffect(() => { reload(); }, []);

  const addTreeTag = async () => {
    if (!newTreeName.trim()) return;
    try {
      await tagApi.createTree({ name: newTreeName.trim(), parent_id: selectedParent });
      setNewTreeName('');
      setSelectedParent(undefined);
      setError('');
      reload();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '创建失败');
    }
  };

  const addContentTag = async () => {
    if (!newContentName.trim()) return;
    try {
      await tagApi.createContent({ name: newContentName.trim(), color: newContentColor });
      setNewContentName('');
      setError('');
      reload();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '创建失败');
    }
  };

  const addStatusDim = async () => {
    if (!newDimKey.trim() || !newDimOptions.trim()) return;
    try {
      const options = newDimOptions.split(',').map((s) => s.trim()).filter(Boolean);
      await tagApi.createStatus({ key: newDimKey.trim(), display_name: newDimKey.trim(), options });
      setNewDimKey('');
      setNewDimOptions('');
      setError('');
      reload();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '创建失败');
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">标签管理</h1>
      {error && <p className="text-sm text-red-500 mb-4 bg-red-50 px-4 py-2 rounded-lg">{error}</p>}

      <div className="grid grid-cols-3 gap-6">
        {/* Tree Tags */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">树形标签</h2>
          <div className="space-y-1 mb-4 max-h-80 overflow-auto">
            {treeTags.map((tag) => (
              <TreeNode key={tag.id} tag={tag} onDelete={(id) => { tagApi.deleteTree(id).then(reload); }} onSelect={setSelectedParent} />
            ))}
            {treeTags.length === 0 && <p className="text-sm text-gray-400">暂无标签</p>}
          </div>
          <div className="border-t border-gray-100 pt-3 space-y-2">
            <input
              value={newTreeName}
              onChange={(e) => setNewTreeName(e.target.value)}
              placeholder="新标签名称"
              className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:ring-1 focus:ring-blue-400"
              onKeyDown={(e) => e.key === 'Enter' && addTreeTag()}
            />
            {selectedParent && (
              <p className="text-xs text-blue-500">
                将创建为子标签
                <button onClick={() => setSelectedParent(undefined)} className="ml-1 underline">取消</button>
              </p>
            )}
            <button onClick={addTreeTag} className="w-full flex items-center justify-center gap-1 py-1.5 text-sm bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100">
              <Plus className="w-4 h-4" /> 添加
            </button>
          </div>
        </div>

        {/* Content Tags */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">内容标签</h2>
          <div className="flex flex-wrap gap-2 mb-4 max-h-80 overflow-auto">
            {contentTags.map((tag) => (
              <span
                key={tag.id}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm text-white group"
                style={{ backgroundColor: tag.color || '#666' }}
              >
                {tag.name}
                <button
                  onClick={() => tagApi.deleteContent(tag.id).then(reload)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </span>
            ))}
            {contentTags.length === 0 && <p className="text-sm text-gray-400">暂无标签</p>}
          </div>
          <div className="border-t border-gray-100 pt-3 space-y-2">
            <div className="flex gap-2">
              <input
                value={newContentName}
                onChange={(e) => setNewContentName(e.target.value)}
                placeholder="标签名称"
                className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:ring-1 focus:ring-blue-400"
                onKeyDown={(e) => e.key === 'Enter' && addContentTag()}
              />
              <div className="relative">
                <input
                  type="color"
                  value={newContentColor}
                  onChange={(e) => setNewContentColor(e.target.value)}
                  className="w-8 h-8 rounded cursor-pointer border-0"
                />
              </div>
            </div>
            <button onClick={addContentTag} className="w-full flex items-center justify-center gap-1 py-1.5 text-sm bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100">
              <Plus className="w-4 h-4" /> 添加
            </button>
          </div>
        </div>

        {/* Status Dimensions */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">状态维度</h2>
          <div className="space-y-3 mb-4 max-h-80 overflow-auto">
            {statusDims.map((dim) => (
              <div key={dim.id} className="p-3 bg-gray-50 rounded-lg group">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-gray-800">{dim.display_name || dim.key}</span>
                  <button
                    onClick={() => tagApi.deleteStatus(dim.id).then(reload)}
                    className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {dim.options.map((opt) => (
                    <span key={opt} className="px-2 py-0.5 text-xs bg-white border border-gray-200 rounded">
                      {opt}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {statusDims.length === 0 && <p className="text-sm text-gray-400">暂无维度</p>}
          </div>
          <div className="border-t border-gray-100 pt-3 space-y-2">
            <input
              value={newDimKey}
              onChange={(e) => setNewDimKey(e.target.value)}
              placeholder="维度名称（如：优先级）"
              className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:ring-1 focus:ring-blue-400"
            />
            <input
              value={newDimOptions}
              onChange={(e) => setNewDimOptions(e.target.value)}
              placeholder="选项（逗号分隔，如：P0,P1,P2）"
              className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg outline-none focus:ring-1 focus:ring-blue-400"
              onKeyDown={(e) => e.key === 'Enter' && addStatusDim()}
            />
            <button onClick={addStatusDim} className="w-full flex items-center justify-center gap-1 py-1.5 text-sm bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100">
              <Plus className="w-4 h-4" /> 添加
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TreeNode({ tag, depth = 0, onDelete, onSelect }: {
  tag: TagTree; depth?: number;
  onDelete: (id: string) => void;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const hasChildren = tag.children && tag.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-1 py-1 px-2 rounded hover:bg-gray-50 group cursor-pointer"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren ? (
          <button onClick={() => setOpen(!open)} className="text-gray-400">
            {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        ) : (
          <span className="w-4" />
        )}
        <span className="text-sm mr-1">{tag.icon || '📁'}</span>
        <span className="text-sm text-gray-700 flex-1" onClick={() => onSelect(tag.id)}>{tag.name}</span>
        <button
          onClick={() => onDelete(tag.id)}
          className="opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
      {open && hasChildren && tag.children.map((child) => (
        <TreeNode key={child.id} tag={child} depth={depth + 1} onDelete={onDelete} onSelect={onSelect} />
      ))}
    </div>
  );
}
