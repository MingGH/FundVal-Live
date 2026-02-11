/**
 * AdminUsers note feature tests — verifies note column display and editing.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';

// Mock the api module
vi.mock('../services/api', () => ({
  getUsers: vi.fn().mockResolvedValue([]),
  createUser: vi.fn().mockResolvedValue({}),
  updateUser: vi.fn().mockResolvedValue({}),
  deleteUser: vi.fn().mockResolvedValue({}),
}));

import AdminUsers from '../pages/AdminUsers';
import { getUsers, createUser, updateUser } from '../services/api';

const mockUsers = [
  { id: 1, username: 'admin', role: 'admin', note: '', is_active: true },
  { id: 2, username: 'alice', role: 'user', note: '大学同学', is_active: true },
  { id: 3, username: 'bob', role: 'user', note: '', is_active: false },
];

describe('AdminUsers note feature', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getUsers.mockResolvedValue(mockUsers);
  });

  it('renders note column header', async () => {
    render(<AdminUsers />);
    await waitFor(() => {
      expect(screen.getByText('备注')).toBeInTheDocument();
    });
  });

  it('displays user notes in the table', async () => {
    render(<AdminUsers />);
    await waitFor(() => {
      expect(screen.getByText('大学同学')).toBeInTheDocument();
    });
  });

  it('shows dash for empty notes', async () => {
    render(<AdminUsers />);
    await waitFor(() => {
      const dashes = screen.getAllByText('—');
      expect(dashes.length).toBe(2); // admin and bob have empty notes
    });
  });

  it('shows edit note buttons for each user', async () => {
    render(<AdminUsers />);
    await waitFor(() => {
      const editButtons = screen.getAllByTitle('编辑备注');
      expect(editButtons.length).toBe(3);
    });
  });

  it('enters edit mode when clicking edit note button', async () => {
    render(<AdminUsers />);
    await waitFor(() => screen.getByText('大学同学'));

    const editButtons = screen.getAllByTitle('编辑备注');
    fireEvent.click(editButtons[1]); // click edit on alice

    // Should show input with current note value
    const input = screen.getByDisplayValue('大学同学');
    expect(input).toBeInTheDocument();
    // Should show save and cancel buttons
    expect(screen.getByTitle('保存')).toBeInTheDocument();
    expect(screen.getByTitle('取消')).toBeInTheDocument();
  });

  it('saves note on confirm click', async () => {
    updateUser.mockResolvedValue({});
    render(<AdminUsers />);
    await waitFor(() => screen.getByText('大学同学'));

    const editButtons = screen.getAllByTitle('编辑备注');
    fireEvent.click(editButtons[1]);

    const input = screen.getByDisplayValue('大学同学');
    fireEvent.change(input, { target: { value: '高中同学' } });
    fireEvent.click(screen.getByTitle('保存'));

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith(2, { note: '高中同学' });
    });
  });

  it('saves note on Enter key', async () => {
    updateUser.mockResolvedValue({});
    render(<AdminUsers />);
    await waitFor(() => screen.getByText('大学同学'));

    const editButtons = screen.getAllByTitle('编辑备注');
    fireEvent.click(editButtons[1]);

    const input = screen.getByDisplayValue('大学同学');
    fireEvent.change(input, { target: { value: '新备注' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(updateUser).toHaveBeenCalledWith(2, { note: '新备注' });
    });
  });

  it('cancels edit on cancel click', async () => {
    render(<AdminUsers />);
    await waitFor(() => screen.getByText('大学同学'));

    const editButtons = screen.getAllByTitle('编辑备注');
    fireEvent.click(editButtons[1]);

    expect(screen.getByDisplayValue('大学同学')).toBeInTheDocument();
    fireEvent.click(screen.getByTitle('取消'));

    // Should exit edit mode, input gone
    expect(screen.queryByDisplayValue('大学同学')).not.toBeInTheDocument();
    // Original text should be back
    expect(screen.getByText('大学同学')).toBeInTheDocument();
  });

  it('cancels edit on Escape key', async () => {
    render(<AdminUsers />);
    await waitFor(() => screen.getByText('大学同学'));

    const editButtons = screen.getAllByTitle('编辑备注');
    fireEvent.click(editButtons[1]);

    const input = screen.getByDisplayValue('大学同学');
    fireEvent.keyDown(input, { key: 'Escape' });

    expect(screen.queryByTitle('保存')).not.toBeInTheDocument();
    expect(screen.getByText('大学同学')).toBeInTheDocument();
  });

  it('includes note field in create form', async () => {
    render(<AdminUsers />);
    await waitFor(() => screen.getByText('用户管理'));

    const noteInput = screen.getByPlaceholderText('备注（可选）');
    expect(noteInput).toBeInTheDocument();
  });

  it('sends note when creating user', async () => {
    createUser.mockResolvedValue({});
    render(<AdminUsers />);
    await waitFor(() => screen.getByText('用户管理'));

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'newuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'pass123' } });
    fireEvent.change(screen.getByPlaceholderText('备注（可选）'), { target: { value: '测试备注' } });
    fireEvent.submit(screen.getByPlaceholderText('用户名').closest('form'));

    await waitFor(() => {
      expect(createUser).toHaveBeenCalledWith({
        username: 'newuser',
        password: 'pass123',
        role: 'user',
        note: '测试备注',
      });
    });
  });

  it('resets note field after successful creation', async () => {
    createUser.mockResolvedValue({});
    render(<AdminUsers />);
    await waitFor(() => screen.getByText('用户管理'));

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'newuser' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'pass123' } });
    fireEvent.change(screen.getByPlaceholderText('备注（可选）'), { target: { value: '测试' } });
    fireEvent.submit(screen.getByPlaceholderText('用户名').closest('form'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('备注（可选）').value).toBe('');
    });
  });
});
