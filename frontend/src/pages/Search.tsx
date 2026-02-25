import { useState } from 'react';
import { Search as SearchIcon, FileText, ExternalLink } from 'lucide-react';
import { searchApi, type SearchResult } from '../api/client';

export default function Search() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const doSearch = async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    setSearched(false);
    try {
      const resp = await searchApi.search(q);
      const list = Array.isArray(resp?.results) ? resp.results : [];
      setResults(list);
      setMessage(resp?.message ?? null);
      setSearched(true);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '搜索请求失败';
      setError(msg);
      setResults([]);
      setSearched(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">语义搜索</h1>

      <div className="flex gap-3 mb-8">
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && doSearch()}
            placeholder="输入自然语言查询，例如：上个月关于投资的笔记"
            className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent text-lg"
          />
        </div>
        <button
          onClick={doSearch}
          disabled={loading || !query.trim()}
          className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 font-medium"
        >
          {loading ? '搜索中...' : '搜索'}
        </button>
      </div>

      {loading && (
        <div className="text-center py-8 text-blue-600">搜索中…</div>
      )}

      {error && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 text-amber-800 px-4 py-3 mb-4">
          {error}
          <span className="text-sm block mt-1">可检查：1) 后端是否运行 2) 设置中 LLM 是否已连接（语义搜索需要）3) 是否有已审核并向量化的实体</span>
        </div>
      )}

      {message && !error && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 text-blue-800 px-4 py-3 mb-4 text-sm">
          {message}
        </div>
      )}

      {searched && !loading && results.length === 0 && !error && (
        <div className="text-center py-12 text-gray-500">
          未找到相关内容，请尝试其他关键词。若从未做过「同步」或「审核通过」，知识库可能为空。
        </div>
      )}

      <div className="space-y-4">
        {Array.isArray(results) && results.map((r, i) => (
          <div key={r.entity_id + i} className="bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <FileText className="w-4 h-4 text-blue-500" />
                  <h3 className="font-semibold text-gray-900">{r.title || '无标题'}</h3>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                    {r.source}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">
                    {r.match_type === 'vector' ? '语义匹配' : '关键词匹配'}
                  </span>
                  {r.distance != null && (
                    <span className="text-xs text-gray-400">
                      相似度: {(1 - r.distance).toFixed(3)}
                    </span>
                  )}
                </div>
                <p className="text-gray-600 text-sm line-clamp-3">{r.content}</p>
                {r.obsidian_path && (
                  <div className="flex items-center gap-1 mt-2 text-xs text-gray-400">
                    <ExternalLink className="w-3 h-3" />
                    {r.obsidian_path}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
