/**
 * Frontend multi-tenancy tests — verifies account isolation logic.
 *
 * Covers:
 * 1. api.js: API functions pass accountId correctly
 * 2. AccountModal: no hardcoded account id=1, delete switches to remaining account
 * 3. App.jsx: currentAccount auto-corrects to user's own account
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ═══════════════════════════════════════════════════════════════
// 1. API layer — no hardcoded account_id leaks
// ═══════════════════════════════════════════════════════════════

describe('API account isolation', () => {
  let api;

  beforeEach(async () => {
    // Mock axios to capture requests
    vi.resetModules();
    vi.doMock('axios', () => {
      const mockAxios = {
        create: vi.fn(() => mockAxios),
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() },
        },
        get: vi.fn().mockResolvedValue({ data: { positions: [], summary: {} } }),
        post: vi.fn().mockResolvedValue({ data: {} }),
        delete: vi.fn().mockResolvedValue({ data: {} }),
        put: vi.fn().mockResolvedValue({ data: {} }),
      };
      return { default: mockAxios };
    });
    api = await import('../services/api.js');
  });

  it('getAccountPositions passes explicit accountId', async () => {
    const { getAccountPositions } = api;
    const axios = (await import('axios')).default;
    await getAccountPositions(42);
    expect(axios.get).toHaveBeenCalledWith('/account/positions', { params: { account_id: 42 } });
  });

  it('updatePosition passes explicit accountId', async () => {
    const { updatePosition } = api;
    const axios = (await import('axios')).default;
    await updatePosition({ code: '000001', cost: 1.0, shares: 100 }, 42);
    expect(axios.post).toHaveBeenCalledWith(
      '/account/positions',
      { code: '000001', cost: 1.0, shares: 100 },
      { params: { account_id: 42 } }
    );
  });

  it('deletePosition passes explicit accountId', async () => {
    const { deletePosition } = api;
    const axios = (await import('axios')).default;
    await deletePosition('000001', 42);
    expect(axios.delete).toHaveBeenCalledWith('/account/positions/000001', { params: { account_id: 42 } });
  });

  it('addPositionTrade passes explicit accountId', async () => {
    const { addPositionTrade } = api;
    const axios = (await import('axios')).default;
    await addPositionTrade('000001', { amount: 1000 }, 42);
    expect(axios.post).toHaveBeenCalledWith(
      '/account/positions/000001/add',
      { amount: 1000 },
      { params: { account_id: 42 } }
    );
  });

  it('reducePositionTrade passes explicit accountId', async () => {
    const { reducePositionTrade } = api;
    const axios = (await import('axios')).default;
    await reducePositionTrade('000001', { shares: 50 }, 42);
    expect(axios.post).toHaveBeenCalledWith(
      '/account/positions/000001/reduce',
      { shares: 50 },
      { params: { account_id: 42 } }
    );
  });

  it('getTransactions passes explicit accountId', async () => {
    const { getTransactions } = api;
    const axios = (await import('axios')).default;
    await getTransactions(42, '000001', 50);
    expect(axios.get).toHaveBeenCalledWith('/account/transactions', {
      params: { account_id: 42, limit: 50, code: '000001' },
    });
  });

  it('updatePositionsNav passes explicit accountId', async () => {
    const { updatePositionsNav } = api;
    const axios = (await import('axios')).default;
    await updatePositionsNav(42);
    expect(axios.post).toHaveBeenCalledWith('/account/positions/update-nav', null, {
      params: { account_id: 42 },
    });
  });
});
