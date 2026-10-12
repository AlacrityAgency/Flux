import { describe, it, expect } from 'vitest';
import { total } from './cart';

describe('cart', () => {
  it.only('focuses one test', () => {
    expect(total([1])).toBe(1);
  });

  it('is empty', () => {});

  it('waits a fixed time', async () => {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    expect(total([])).toBe(0);
  });

  it('never asserts', () => {
    total([1, 2]);
  });

  it.skip('skipped for now', () => {
    expect(total([2])).toBe(2);
  });

  it('calls a real service', async () => {
    const res = await fetch('https://api.github.com/repos/foo/bar');
    expect(res.ok).toBe(true);
  });
});
