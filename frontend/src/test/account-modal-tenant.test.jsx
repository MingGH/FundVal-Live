/**
 * AccountModal multi-tenancy tests — verifies no hardcoded account id=1.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';

// Mock the api module
vi.mock('../services/api', () => ({
  createAccount: vi.fn().mockResolvedValue({}),
  updateAccount: vi.fn().mockResolvedValue({}),
  deleteAccount: vi.fn().mockResolvedValue({}),
}));

import { AccountModal } from '../components/AccountModal';

describe('AccountModal tenant isolation', () => {
  const defaultProps = {
    onClose: vi.fn(),
    onRefresh: vi.fn(),
    onSwitch: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Suppress window.confirm in tests
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('does not show "系统默认" label for any account', () => {
    const accounts = [
      { id: 5, name: '我的账户', description: '' },
      { id: 8, name: '备用账户', description: '' },
    ];

    render(
      <AccountModal accounts={accounts} currentAccount={5} {...defaultProps} />
    );

    expect(screen.queryByText('系统默认')).not.toBeInTheDocument();
  });

  it('allows editing any account regardless of id', () => {
    const accounts = [
      { id: 5, name: '我的账户', description: '' },
      { id: 8, name: '备用账户', description: '' },
    ];

    render(
      <AccountModal accounts={accounts} currentAccount={5} {...defaultProps} />
    );

    // Both accounts should have edit buttons
    const editButtons = screen.getAllByTitle('编辑');
    expect(editButtons.length).toBe(2);
  });

  it('shows delete button when multiple accounts exist', () => {
    const accounts = [
      { id: 5, name: '我的账户', description: '' },
      { id: 8, name: '备用账户', description: '' },
    ];

    render(
      <AccountModal accounts={accounts} currentAccount={5} {...defaultProps} />
    );

    const deleteButtons = screen.getAllByTitle('删除');
    expect(deleteButtons.length).toBe(2);
  });

  it('hides delete button when only one account exists', () => {
    const accounts = [
      { id: 5, name: '唯一账户', description: '' },
    ];

    render(
      <AccountModal accounts={accounts} currentAccount={5} {...defaultProps} />
    );

    expect(screen.queryByTitle('删除')).not.toBeInTheDocument();
    // But edit should still be available
    expect(screen.getByTitle('编辑')).toBeInTheDocument();
  });

  it('switches to remaining account on delete, not hardcoded id=1', async () => {
    const { deleteAccount } = await import('../services/api');
    deleteAccount.mockResolvedValue({});

    const accounts = [
      { id: 5, name: '账户A', description: '' },
      { id: 8, name: '账户B', description: '' },
    ];

    render(
      <AccountModal accounts={accounts} currentAccount={5} {...defaultProps} />
    );

    // Click delete on the first account (id=5, which is currentAccount)
    const deleteButtons = screen.getAllByTitle('删除');
    fireEvent.click(deleteButtons[0]);

    // Wait for async
    await vi.waitFor(() => {
      // Should switch to account 8 (the remaining one), NOT hardcoded 1
      expect(defaultProps.onSwitch).toHaveBeenCalledWith(8);
    });
  });
});
