import { useState } from 'react';
import { Search as SearchIcon, FileText, ExternalLink } from 'lucide-react';
import { searchApi, type SearchResult } from '../api/client';

export default function Search() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const doSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const resp = await searchApi.search(query);
      setResults(resp.results);
      setSearched(true);
    } catch {
      setResults([]);
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

      {searched && results.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          未找到相关内容，请尝试其他关键词
        </div>
      )}

      <div className="space-y-4">
        {results.map((r, i) => (
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
