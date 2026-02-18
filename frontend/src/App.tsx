import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { authApi } from './api/client';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import TagManager from './pages/TagManager';
import Entities from './pages/Entities';
import UserManage from './pages/UserManage';
import Ingest from './pages/Ingest';
import ReviewQueue from './pages/ReviewQueue';
import Settings from './pages/Settings';

export default function App() {
  const [authMode, setAuthMode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    authApi.getMode()
      .then(({ auth_mode }) => setAuthMode(auth_mode))
      .catch(() => setAuthMode('single'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-gray-400">加载中...</div>
      </div>
    );
  }

  const needsLogin = authMode === 'multi' && !localStorage.getItem('token');

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        {needsLogin ? (
          <Route path="*" element={<Navigate to="/login" replace />} />
        ) : (
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/ingest" element={<Ingest />} />
            <Route path="/review" element={<ReviewQueue />} />
            <Route path="/entities" element={<Entities />} />
            <Route path="/tags" element={<TagManager />} />
            <Route path="/users" element={<UserManage />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        )}
      </Routes>
    </BrowserRouter>
  );
}
