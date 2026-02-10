import React, { useState, useEffect } from 'react';
import { UserPlus, Trash2, ToggleLeft, ToggleRight } from 'lucide-react';
import { getUsers, createUser, updateUser, deleteUser } from '../services/api';

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ username: '', password: '', role: 'user' });
  const [error, setError] = useState('');
  const [createdInfo, setCreatedInfo] = useState(null);

  const load = async () => {
    try { setUsers(await getUsers()); } catch { setError('加载用户列表失败'); }
  };
  useEffect(() => { load(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError('');
    setCreatedInfo(null);
    try {
      await createUser(form);
      setCreatedInfo({ username: form.username, password: form.password });
      setForm({ username: '', password: '', role: 'user' });
      load();
    } catch (err) { setError(err.response?.data?.detail || '创建失败'); }
  };

  const toggleActive = async (u) => {
    try { await updateUser(u.id, { is_active: !u.is_active }); load(); }
    catch (err) { setError(err.response?.data?.detail || '操作失败'); }
  };

  const handleDelete = async (u) => {
    if (!confirm(`确定删除用户 ${u.username}？`)) return;
    try { await deleteUser(u.id); load(); }
    catch (err) { setError(err.response?.data?.detail || '删除失败'); }
  };

  const cellStyle = { padding: '8px 12px', borderBottom: '1px solid #eee', textAlign: 'left' };

  return (
    <div style={{ padding: 24, maxWidth: 700 }}>
      <h3 style={{ marginBottom: 16 }}>用户管理</h3>
      {error && <div style={{ color: '#e53e3e', marginBottom: 12, fontSize: 14 }}>{error}</div>}

      <form onSubmit={handleCreate} style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
        <input placeholder="用户名" value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required
          style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #d0d0d0', flex: 1, minWidth: 120 }} />
        <input placeholder="密码" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required
          style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #d0d0d0', flex: 1, minWidth: 120 }} />
        <select value={form.role} onChange={e => setForm({ ...form, role: e.target.value })}
          style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #d0d0d0' }}>
          <option value="user">普通用户</option>
          <option value="admin">管理员</option>
        </select>
        <button type="submit" style={{ padding: '6px 14px', borderRadius: 6, border: 'none', background: '#3182ce', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
          <UserPlus size={16} /> 创建
        </button>
      </form>

      {createdInfo && (
        <div style={{ background: '#f0fff4', border: '1px solid #c6f6d5', borderRadius: 8, padding: '12px 16px', marginBottom: 20, fontSize: 14 }}>
          <div style={{ fontWeight: 600, marginBottom: 6, color: '#276749' }}>✅ 用户创建成功</div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <span>用户名：<strong>{createdInfo.username}</strong></span>
            <span>密码：<strong>{createdInfo.password}</strong></span>
            <button
              onClick={() => {
                navigator.clipboard.writeText(`用户名: ${createdInfo.username}\n密码: ${createdInfo.password}`);
                alert('已复制到剪贴板');
              }}
              style={{ padding: '2px 10px', borderRadius: 4, border: '1px solid #c6f6d5', background: '#fff', cursor: 'pointer', fontSize: 13 }}
            >
              复制
            </button>
            <button
              onClick={() => setCreatedInfo(null)}
              style={{ padding: '2px 10px', borderRadius: 4, border: '1px solid #e2e8f0', background: '#fff', cursor: 'pointer', fontSize: 13 }}
            >
              关闭
            </button>
          </div>
        </div>
      )}

      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#f7f7f7' }}>
            <th style={cellStyle}>ID</th><th style={cellStyle}>用户名</th><th style={cellStyle}>角色</th><th style={cellStyle}>状态</th><th style={cellStyle}>操作</th>
          </tr>
        </thead>
        <tbody>
          {users.map(u => (
            <tr key={u.id}>
              <td style={cellStyle}>{u.id}</td>
              <td style={cellStyle}>{u.username}</td>
              <td style={cellStyle}>{u.role}</td>
              <td style={cellStyle}>{u.is_active ? '✅ 启用' : '🚫 禁用'}</td>
              <td style={cellStyle}>
                <button onClick={() => toggleActive(u)} title={u.is_active ? '禁用' : '启用'}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', marginRight: 8 }}>
                  {u.is_active ? <ToggleRight size={18} color="#38a169" /> : <ToggleLeft size={18} color="#a0a0a0" />}
                </button>
                <button onClick={() => handleDelete(u)} title="删除"
                  style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                  <Trash2 size={16} color="#e53e3e" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
