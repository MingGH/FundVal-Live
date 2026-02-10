/**
 * Tests for the account correction logic extracted from App.jsx.
 * Verifies that currentAccount is auto-corrected when it doesn't belong to the user.
 */
import { describe, it, expect } from 'vitest';

/**
 * Pure function that mirrors the account correction logic in App.jsx loadAccounts callback.
 * Given a list of user accounts and the current account id, returns the corrected account id.
 */
function correctAccountId(accounts, currentAccount) {
  if (!accounts || accounts.length === 0) return currentAccount;
  const validIds = new Set(accounts.map(a => a.id));
  if (currentAccount === 0) return currentAccount; // "all accounts" view is always valid
  if (validIds.has(currentAccount)) return currentAccount;
  return accounts[0].id;
}

describe('Account ID correction logic', () => {
  it('keeps currentAccount if it belongs to user', () => {
    const accounts = [{ id: 5 }, { id: 8 }];
    expect(correctAccountId(accounts, 5)).toBe(5);
    expect(correctAccountId(accounts, 8)).toBe(8);
  });

  it('corrects to first account if currentAccount does not belong to user', () => {
    const accounts = [{ id: 5 }, { id: 8 }];
    // account_id=1 belongs to admin, not this user
    expect(correctAccountId(accounts, 1)).toBe(5);
  });

  it('preserves aggregated view (account_id=0)', () => {
    const accounts = [{ id: 5 }];
    expect(correctAccountId(accounts, 0)).toBe(0);
  });

  it('handles empty accounts list gracefully', () => {
    expect(correctAccountId([], 1)).toBe(1);
    expect(correctAccountId(null, 1)).toBe(1);
  });

  it('corrects any non-existent account id', () => {
    const accounts = [{ id: 10 }, { id: 20 }];
    expect(correctAccountId(accounts, 999)).toBe(10);
  });
});

/**
 * Pure function that mirrors the fetchAccountCodes guard in App.jsx.
 * Returns true if it's safe to fetch, false if should skip.
 */
function shouldFetchAccountCodes(accounts, currentAccount) {
  if (accounts.length === 0) return false; // Wait for accounts to load
  if (currentAccount === 0) return true; // Aggregated view is always ok
  const validIds = new Set(accounts.map(a => a.id));
  return validIds.has(currentAccount);
}

describe('fetchAccountCodes guard logic', () => {
  it('blocks fetch when accounts not loaded yet', () => {
    expect(shouldFetchAccountCodes([], 1)).toBe(false);
  });

  it('allows fetch for valid account', () => {
    const accounts = [{ id: 5 }, { id: 8 }];
    expect(shouldFetchAccountCodes(accounts, 5)).toBe(true);
  });

  it('blocks fetch for invalid account (prevents 403)', () => {
    const accounts = [{ id: 5 }, { id: 8 }];
    expect(shouldFetchAccountCodes(accounts, 1)).toBe(false);
  });

  it('allows fetch for aggregated view', () => {
    const accounts = [{ id: 5 }];
    expect(shouldFetchAccountCodes(accounts, 0)).toBe(true);
  });
});

/**
 * Pure function that mirrors the AccountModal delete-switch logic.
 * Returns the account id to switch to after deleting the current account.
 */
function getAccountAfterDelete(accounts, deletedId, currentAccount) {
  if (currentAccount !== deletedId) return currentAccount;
  const remaining = accounts.filter(a => a.id !== deletedId);
  return remaining.length > 0 ? remaining[0].id : currentAccount;
}

describe('Account delete switch logic', () => {
  it('stays on current account if a different one is deleted', () => {
    const accounts = [{ id: 5 }, { id: 8 }];
    expect(getAccountAfterDelete(accounts, 8, 5)).toBe(5);
  });

  it('switches to remaining account when current is deleted', () => {
    const accounts = [{ id: 5 }, { id: 8 }];
    expect(getAccountAfterDelete(accounts, 5, 5)).toBe(8);
  });

  it('does NOT switch to hardcoded id=1', () => {
    const accounts = [{ id: 5 }, { id: 8 }];
    const result = getAccountAfterDelete(accounts, 5, 5);
    // The key assertion: should be 8, not 1
    expect(result).not.toBe(1);
    expect(result).toBe(8);
  });

  it('handles single account (should not happen due to backend guard)', () => {
    const accounts = [{ id: 5 }];
    // If somehow the only account is deleted, keep current
    expect(getAccountAfterDelete(accounts, 5, 5)).toBe(5);
  });
});
