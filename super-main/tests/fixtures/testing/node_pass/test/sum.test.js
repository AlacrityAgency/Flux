import { test } from 'node:test';
import assert from 'node:assert/strict';
import { sum } from '../sum.js';

test('sums numbers', () => {
  assert.equal(sum([1, 2, 3]), 6);
});

test('empty list sums to zero', () => {
  assert.equal(sum([]), 0);
});
