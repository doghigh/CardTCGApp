import { test } from 'node:test';
import assert from 'node:assert/strict';
import { monthKey, isOverCap } from '../src/cap.js';

test('monthKey formats year-month, zero-padded', () => {
  assert.equal(monthKey(new Date(Date.UTC(2026, 6, 12))), 'trial:2026-07');
  assert.equal(monthKey(new Date(Date.UTC(2026, 0, 3))), 'trial:2026-01');
});

test('isOverCap is true only at or above the cap', () => {
  assert.equal(isOverCap(0, 10), false);
  assert.equal(isOverCap(9, 10), false);
  assert.equal(isOverCap(10, 10), true);
  assert.equal(isOverCap(11, 10), true);
});
