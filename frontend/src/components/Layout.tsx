import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Brain, Tags, FileText, Users, LayoutDashboard, Download, ClipboardCheck, Settings, Search, Share2, MessageSquare, ArrowUpCircle } from 'lucide-react';
import { reviewApi, versionApi } from '../api/client';

const NAV_ITEMS = [
  { path: '/', label: '仪表盘', icon: LayoutDashboard },
  { path: '/ingest', label: '数据摄入', icon: Download },
  { path: '/review', label: '审核队列', icon: ClipboardCheck, badge: true },
  { path: '/search', label: '语义搜索', icon: Search },
  { path: '/graph', label: '知识图谱', icon: Share2 },
  { path: '/chat', label: '智能对话', icon: MessageSquare },
  { path: '/entities', label: '实体管理', icon: FileText },
  { path: '/tags', label: '标签管理', icon: Tags },
  { path: '/users', label: '用户管理', icon: Users },
  { path: '/settings', label: '设置', icon: Settings },
];

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [reviewCount, setReviewCount] = useState(0);
  const [version, setVersion] = useState('');
  const [hasUpdate, setHasUpdate] = useState(false);

  useEffect(() => {
    reviewApi.getCount().then(r => setReviewCount(r.count)).catch(() => {});
    const interval = setInterval(() => {
      reviewApi.getCount().then(r => setReviewCount(r.count)).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    versionApi.getVersion().then(r => setVersion(r.version)).catch(() => {});
    const check = () => versionApi.checkUpdate().then(r => setHasUpdate(r.has_update)).catch(() => {});
    check();
    const interval = setInterval(check, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-56 bg-gray-900 text-white flex flex-col shrink-0">
        <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-700">
          <Brain className="w-6 h-6 text-blue-400" />
          <span className="font-bold text-lg">第二大脑</span>
        </div>
        <nav className="flex-1 py-3">
          {NAV_ITEMS.map((item) => {
            const active = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg transition-colors ${
                  active ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`}
              >
                <item.icon className="w-5 h-5" />
                <span className="text-sm flex-1">{item.label}</span>
                {item.badge && reviewCount > 0 && (
                  <span className="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                    {reviewCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        <div
          className={`px-4 py-3 border-t border-gray-700 text-xs flex items-center gap-2 ${hasUpdate ? 'text-amber-400 cursor-pointer hover:text-amber-300' : 'text-gray-500'}`}
          onClick={() => hasUpdate && navigate('/settings?tab=version')}
        >
          <span>v{version || '...'}</span>
          {hasUpdate && (
            <>
              <ArrowUpCircle className="w-3.5 h-3.5" />
              <span>有新版本</span>
            </>
          )}
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
