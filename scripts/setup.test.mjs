import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {normalizedTarget, normalizedProxy, configLabel} from './setup-config.mjs';

const entry=path.join(path.dirname(fileURLToPath(import.meta.url)),'setup.mjs');
const exec=arg=>spawnSync(process.execPath,[entry,arg],{encoding:'utf8',env:{...process.env,NO_COLOR:'1'},timeout:15000});

test('domain-only target adds https',()=>{
  assert.equal(normalizedTarget('labprivate.com'),'https://labprivate.com/');
  assert.equal(normalizedTarget('sub.labprivate.com/path'),'https://sub.labprivate.com/path');
});
test('local domains use http by default; preserve explicit scheme',()=>{
  assert.equal(normalizedTarget('localhost:3000'),'http://localhost:3000/');
  assert.equal(normalizedTarget('192.168.1.10:8080'),'http://192.168.1.10:8080/');
  assert.equal(normalizedTarget('https://localhost:3000'),'https://localhost:3000/');
});
test('deny public Meta domains and credentialed targets',()=>{
  assert.throws(()=>normalizedTarget('instagram.com'),/tidak termasuk/);
  assert.throws(()=>normalizedTarget('www.instagram.com'),/tidak termasuk/);
  assert.throws(()=>normalizedTarget('https://user:password@lab.test'),/tanpa kredensial/);
  assert.throws(()=>normalizedTarget('ftp://labprivate.com'),/http:\/\//);
});
test('proxy URL parse and credential redaction',()=>{
  assert.deepEqual(normalizedProxy('127.0.0.1:8000'),{server:'http://127.0.0.1:8000',username:'',password:'',label:'http://127.0.0.1:8000'});
  assert.deepEqual(normalizedProxy('socks5://alice:p%40ss@localhost:9050'),{server:'socks5://localhost:9050',username:'alice',password:'p@ss',label:'socks5://localhost:9050'});
});
test('proxy requires port; no paths',()=>{
  assert.throws(()=>normalizedProxy('someproxy.example'),/Proxy harus/);
  assert.throws(()=>normalizedProxy('http://example.com:123/path'),/Proxy harus/);
});
test('configuration labels show both toggles',()=>{
  assert.match(configLabel({headless:false,proxy:false}),/Headless OFF/);
  assert.match(configLabel({headless:true,proxy:true}),/Proxy ON/);
});
test('main menu preview lists exactly requested choices',()=>{
  const r=exec('--preview');assert.equal(r.status,0,r.stderr);
  assert.match(r.stdout,/USERNAME LAB/);
  assert.match(r.stdout,/CONFIG/);
  assert.match(r.stdout,/EXIT/);
  assert.doesNotMatch(r.stdout,/SESSION LAB|WEB DASHBOARD|DIAGNOSTICS/);
  assert.doesNotMatch(r.stdout,/\x1b\[/);
});
test('health check and no-TTY usage succeed',()=>{
  const r=exec('--check');assert.equal(r.status,0,r.stderr);
  assert.match(r.stdout,/SYSTEM HEALTH/);
  const nonTTY=spawnSync(process.execPath,[entry],{encoding:'utf8',timeout:15000});
  assert.equal(nonTTY.status,0,nonTTY.stderr);
  assert.match(nonTTY.stdout,/npm run setup/);
});
