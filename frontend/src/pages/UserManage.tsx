import { useEffect, useState } from 'react';
import { authApi, type User } from '../api/client';
import { Plus, Trash2, Shield, UserCheck } from 'lucide-react';

export default function UserManage() {
  const [users, setUsers] = useState<User[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ username: '', password: '', display_name: '', role: 'member' });
  const [error, setError] = useState('');

  const reload = () => { authApi.listUsers().then(setUsers).catch(() => {}); };

  useEffect(reload, []);

  const handleAdd = async () => {
    setError('');
    try {
      await authApi.createUser(form);
      setShowAdd(false);
      setForm({ username: '', password: '', display_name: '', role: 'member' });
      reload();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '创建失败');
    }
  };

  const toggleActive = async (user: User) => {
    await authApi.updateUser(user.id, { is_active: !user.is_active });
    reload();
  };

  const toggleRole = async (user: User) => {
    const newRole = user.role === 'admin' ? 'member' : 'admin';
    await authApi.updateUser(user.id, { role: newRole });
    reload();
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">用户管理</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> 添加用户
        </button>
      </div>

      {showAdd && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
          <h3 className="font-medium text-gray-800 mb-3">新建用户</h3>
          {error && <p className="text-sm text-red-500 mb-2">{error}</p>}
          <div className="grid grid-cols-2 gap-3 mb-3">
            <input
              placeholder="用户名"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none focus:ring-1 focus:ring-blue-400"
            />
            <input
              placeholder="密码"
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none focus:ring-1 focus:ring-blue-400"
            />
            <input
              placeholder="显示名称"
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none focus:ring-1 focus:ring-blue-400"
            />
            <select
              value={form.role}
              onChange={(e) => setForm({ ...form, role: e.target.value })}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm outline-none focus:ring-1 focus:ring-blue-400"
            >
              <option value="member">员工</option>
              <option value="admin">管理员</option>
            </select>
          </div>
          <button onClick={handleAdd} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            创建
          </button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">用户</th>
              <th className="text-left px-4 py-3 font-medium">角色</th>
              <th className="text-left px-4 py-3 font-medium">状态</th>
              <th className="text-left px-4 py-3 font-medium">最后登录</th>
              <th className="text-right px-4 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id} className="border-t border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-800">{user.display_name || user.username}</div>
                  <div className="text-xs text-gray-400">@{user.username}</div>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${
                    user.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {user.role === 'admin' ? <Shield className="w-3 h-3" /> : <UserCheck className="w-3 h-3" />}
                    {user.role === 'admin' ? '管理员' : '员工'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-block w-2 h-2 rounded-full mr-1 ${user.is_active ? 'bg-green-400' : 'bg-gray-300'}`} />
                  <span className="text-xs">{user.is_active ? '启用' : '禁用'}</span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-400">{user.last_login_at || '从未登录'}</td>
                <td className="px-4 py-3 text-right space-x-2">
                  <button
                    onClick={() => toggleRole(user)}
                    className="text-xs text-blue-500 hover:underline"
                  >
                    切换角色
                  </button>
                  <button
                    onClick={() => toggleActive(user)}
                    className="text-xs text-orange-500 hover:underline"
                  >
                    {user.is_active ? '禁用' : '启用'}
                  </button>
                  <button
                    onClick={() => { if (confirm('确定删除？')) authApi.deleteUser(user.id).then(reload); }}
                    className="text-xs text-red-500 hover:underline"
                  >
                    删除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
