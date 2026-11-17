// node --test tests_lab_target.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveLabTargetFromUsername, normalizedTarget, labBaseUrl } from './scripts/setup-config.mjs';

test('plain username → default lab route', async () => {
  const u = await resolveLabTargetFromUsername('rizkyasep_sutrisna');
  assert.equal(u, labBaseUrl() + '/u/rizkyasep_sutrisna');
});

test('user@127.0.0.1:3000 → explicit origin', async () => {
  const u = await resolveLabTargetFromUsername('demo@127.0.0.1:3000');
  assert.equal(u, 'http://127.0.0.1:3000/u/demo');
});

test('url pasted in username field is rejected', async () => {
  await assert.rejects(
    () => resolveLabTargetFromUsername('https://www.instagram.com/rizkyasep_sutrisna'),
    /username lab; URL tidak diperbolehkan/,
  );
});

test('malformed username rejected', async () => {
  await assert.rejects(() => resolveLabTargetFromUsername('..'), /huruf\/angka/);
});

test('user@public-ip rejected', async () => {
  await assert.rejects(
    () => resolveLabTargetFromUsername('demo@8.8.8.8:3000'),
    /localhost \/ IP privat|Instagram\/Meta/,
  );
});

test('normalizedTarget still blocks instagram.com', () => {
  assert.throws(() => normalizedTarget('https://www.instagram.com/x'), /Instagram\/Meta/);
});

test('normalizedTarget accepts localhost', () => {
  const v = normalizedTarget('127.0.0.1:3000');
  assert.ok(v.startsWith('http://127.0.0.1:3000'));
});
