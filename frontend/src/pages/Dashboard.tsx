import { useEffect, useState } from 'react';
import { tagApi, entityApi, reviewApi, type Entity } from '../api/client';
import { FileText, Tags, Clock } from 'lucide-react';

export default function Dashboard() {
  const [tagCount, setTagCount] = useState(0);
  const [entityCount, setEntityCount] = useState(0);
  const [reviewCount, setReviewCount] = useState(0);
  const [recentEntities, setRecentEntities] = useState<Entity[]>([]);

  useEffect(() => {
    tagApi.listContent().then((t) => setTagCount(t.length)).catch(() => {});
    entityApi.list({ page: 1 }).then((e) => {
      setEntityCount(e.length);
      setRecentEntities(e.slice(0, 5));
    }).catch(() => {});
    reviewApi.getCount().then(r => setReviewCount(r.count)).catch(() => {});
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">仪表盘</h1>

      <div className="grid grid-cols-3 gap-4 mb-8">
        <StatCard icon={<Tags className="w-5 h-5 text-blue-500" />} label="内容标签" value={tagCount} />
        <StatCard icon={<FileText className="w-5 h-5 text-green-500" />} label="实体总数" value={entityCount} />
        <StatCard icon={<Clock className="w-5 h-5 text-orange-500" />} label="待审核" value={reviewCount} />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">最近实体</h2>
        {recentEntities.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无数据</p>
        ) : (
          <div className="space-y-2">
            {recentEntities.map((e) => (
              <div key={e.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                <div>
                  <span className="text-sm font-medium text-gray-800">{e.title}</span>
                  <span className="ml-2 text-xs text-gray-400">{e.source}</span>
                </div>
                <span className="text-xs text-gray-400">{e.updated_at}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4">
      <div className="p-2 bg-gray-50 rounded-lg">{icon}</div>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  );
}
