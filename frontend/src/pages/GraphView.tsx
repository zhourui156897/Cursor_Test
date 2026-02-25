import { useEffect, useState, useRef, useCallback } from 'react';
import { Share2, BarChart3, RefreshCw } from 'lucide-react';
import { graphApi, type GraphData, type GraphStats } from '../api/client';

export default function GraphView() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, g] = await Promise.all([graphApi.stats(), graphApi.overview(80)]);
      setStats(s);
      setGraphData(g);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '图服务请求失败';
      setError(msg);
      setStats({ available: false, node_count: 0, relationship_count: 0, error: msg });
      setGraphData({ nodes: [], edges: [] });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!graphData || !canvasRef.current) return;
    drawGraph(canvasRef.current, graphData);
  }, [graphData]);

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400">加载图谱数据...</div>;

  if (!stats?.available) {
    return (
      <div className="text-center py-20">
        <Share2 className="w-16 h-16 mx-auto mb-4 text-gray-300" />
        <h2 className="text-xl font-semibold text-gray-600 mb-2">知识图谱未就绪</h2>
        <p className="text-gray-400 mb-2">Neo4j 未连接或暂无数据。审核通过实体后将自动构建图谱。</p>
        {(error || stats?.error) && (
          <p className="text-sm text-amber-600 max-w-md mx-auto">{error || stats?.error}</p>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">知识图谱</h1>
        <button onClick={loadData} className="flex items-center gap-2 px-4 py-2 text-gray-600 border rounded-lg hover:bg-gray-50">
          <RefreshCw className="w-4 h-4" /> 刷新
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white border rounded-xl p-4 text-center">
          <BarChart3 className="w-6 h-6 mx-auto mb-1 text-blue-500" />
          <div className="text-2xl font-bold text-gray-900">{stats.node_count}</div>
          <div className="text-sm text-gray-500">实体节点</div>
        </div>
        <div className="bg-white border rounded-xl p-4 text-center">
          <Share2 className="w-6 h-6 mx-auto mb-1 text-green-500" />
          <div className="text-2xl font-bold text-gray-900">{stats.relationship_count}</div>
          <div className="text-sm text-gray-500">关系边</div>
        </div>
        <div className="bg-white border rounded-xl p-4 text-center">
          <div className="w-6 h-6 mx-auto mb-1 rounded-full bg-green-400" />
          <div className="text-2xl font-bold text-gray-900">在线</div>
          <div className="text-sm text-gray-500">Neo4j 状态</div>
        </div>
      </div>

      <div className="bg-white border rounded-xl overflow-hidden" style={{ height: '500px' }}>
        {graphData && graphData.nodes.length > 0 ? (
          <canvas ref={canvasRef} className="w-full h-full" />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-400">
            暂无图谱数据，审核通过实体后将自动构建
          </div>
        )}
      </div>
    </div>
  );
}

function drawGraph(canvas: HTMLCanvasElement, data: GraphData) {
  const rect = canvas.parentElement!.getBoundingClientRect();
  canvas.width = rect.width * 2;
  canvas.height = rect.height * 2;
  canvas.style.width = rect.width + 'px';
  canvas.style.height = rect.height + 'px';
  const ctx = canvas.getContext('2d')!;
  ctx.scale(2, 2);
  const W = rect.width, H = rect.height;

  const positions = new Map<string, { x: number; y: number }>();
  data.nodes.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / data.nodes.length;
    const r = Math.min(W, H) * 0.35;
    positions.set(n.id, { x: W / 2 + r * Math.cos(angle), y: H / 2 + r * Math.sin(angle) });
  });

  for (let iter = 0; iter < 50; iter++) {
    data.nodes.forEach(n => {
      const p = positions.get(n.id)!;
      data.nodes.forEach(m => {
        if (n.id === m.id) return;
        const q = positions.get(m.id)!;
        const dx = p.x - q.x, dy = p.y - q.y;
        const d = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const f = 500 / d;
        p.x += (dx / d) * f * 0.1;
        p.y += (dy / d) * f * 0.1;
      });
    });
    data.edges.forEach(e => {
      const a = positions.get(e.source), b = positions.get(e.target);
      if (!a || !b) return;
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy);
      const f = (d - 120) * 0.02;
      a.x += (dx / d) * f; a.y += (dy / d) * f;
      b.x -= (dx / d) * f; b.y -= (dy / d) * f;
    });
    data.nodes.forEach(n => {
      const p = positions.get(n.id)!;
      p.x = Math.max(40, Math.min(W - 40, p.x));
      p.y = Math.max(40, Math.min(H - 40, p.y));
    });
  }

  ctx.clearRect(0, 0, W, H);

  data.edges.forEach(e => {
    const a = positions.get(e.source), b = positions.get(e.target);
    if (!a || !b) return;
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = '#ddd'; ctx.lineWidth = 1; ctx.stroke();
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    ctx.fillStyle = '#bbb'; ctx.font = '9px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(e.type, mx, my - 4);
  });

  const colors: Record<string, string> = { upload: '#3b82f6', apple_notes: '#f59e0b', apple_reminders: '#10b981', extraction: '#8b5cf6' };
  data.nodes.forEach(n => {
    const p = positions.get(n.id)!;
    const color = colors[n.source] || '#6b7280';
    ctx.beginPath(); ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
    ctx.fillStyle = color; ctx.fill();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
    ctx.fillStyle = '#374151'; ctx.font = '11px sans-serif'; ctx.textAlign = 'center';
    const label = n.title.length > 12 ? n.title.slice(0, 12) + '…' : n.title;
    ctx.fillText(label, p.x, p.y + 20);
  });
}
