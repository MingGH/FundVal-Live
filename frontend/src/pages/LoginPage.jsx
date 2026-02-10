import React, { useState } from 'react';
import { LogIn } from 'lucide-react';
import { login } from '../services/api';

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await login(username, password);
      onLogin(user);
    } catch (err) {
      setError(err.response?.data?.detail || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f5f5f5' }}>
      <form onSubmit={handleSubmit} style={{ background: '#fff', padding: 32, borderRadius: 12, boxShadow: '0 2px 12px rgba(0,0,0,0.1)', width: 340 }}>
        <h2 style={{ textAlign: 'center', marginBottom: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <LogIn size={22} /> FundVal 登录
        </h2>
        {error && <div style={{ color: '#e53e3e', marginBottom: 12, textAlign: 'center', fontSize: 14 }}>{error}</div>}
        <div style={{ marginBottom: 16 }}>
          <label htmlFor="login-username" style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>用户名</label>
          <input id="login-username" type="text" value={username} onChange={e => setUsername(e.target.value)}
            autoComplete="username" required autoFocus
            style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #d0d0d0', boxSizing: 'border-box' }} />
        </div>
        <div style={{ marginBottom: 24 }}>
          <label htmlFor="login-password" style={{ display: 'block', marginBottom: 4, fontSize: 14 }}>密码</label>
          <input id="login-password" type="password" value={password} onChange={e => setPassword(e.target.value)}
            autoComplete="current-password" required
            style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #d0d0d0', boxSizing: 'border-box' }} />
        </div>
        <button type="submit" disabled={loading}
          style={{ width: '100%', padding: '10px 0', borderRadius: 6, border: 'none', background: '#3182ce', color: '#fff', fontSize: 16, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1 }}>
          {loading ? '登录中...' : '登录'}
        </button>
      </form>
    </div>
  );
}
