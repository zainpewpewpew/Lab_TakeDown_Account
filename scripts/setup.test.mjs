import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
const entry = path.join(import.meta.dirname, 'setup.mjs');
function run(flag) {return spawnSync(process.execPath, [entry, flag], {encoding:'utf8',timeout:15000,env:{...process.env,NO_COLOR:'1'}});}
test('Ghoster.ai branded help', () => {const r=run('--help');assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/Ghoster\.ai/);});
test('diagnostic command exits successfully', () => {const r=run('--check');assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/SYSTEM HEALTH/);});
test('no ANSI escapes for redirected output', () => {const r=run('--help');assert.doesNotMatch(r.stdout,/\x1b\[/);});
test('non-interactive execution shows usage rather than hanging', () => {const r=spawnSync(process.execPath,[entry],{encoding:'utf8',timeout:15000});assert.equal(r.status,0,r.stderr);assert.match(r.stdout,/npm run setup/);});
