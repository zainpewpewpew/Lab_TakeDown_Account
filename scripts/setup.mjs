#!/usr/bin/env node
/** Ghoster.ai — local/private lab terminal control. No third-party automation. */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { createInterface } from 'node:readline/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import process from 'node:process';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const VENV = path.join(ROOT, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const flags = new Set(process.argv.slice(2));
const colorEnabled = Boolean(process.stdout.isTTY && process.env.NO_COLOR === undefined && process.env.TERM !== 'dumb');
const motionEnabled = colorEnabled && process.env.REDUCED_MOTION !== '1' && !process.env.CI && !flags.has('--no-animation');
const colors = { cyan:'\x1b[38;2;52;229;247m', pink:'\x1b[38;2;255;92;207m', green:'\x1b[38;2;113;250;178m', blue:'\x1b[38;2;120;157;255m', yellow:'\x1b[38;2;255;201;110m', red:'\x1b[38;2;255;108;136m', dim:'\x1b[38;2;151;164;185m' };
const paint = (s, c) => colorEnabled ? (colors[c] || '') + s + '\x1b[0m' : s;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const time = () => new Date().toLocaleTimeString('en-GB', {hour12: false});
let count = 0;
function log(stage, message, tone='cyan') {
  console.log(paint(time(), 'dim') + ' ' + paint('[' + String(++count).padStart(2, '0') + ']', 'dim') + ' ' + paint(('◆ ' + stage).padEnd(17), tone) + ' ' + message);
}
function banner() {
  return [
    ' ╔═══════════════════════════════════════════════════════════════════╗',
    ' ║                                                                   ║',
    ' ║                   G H O S T E R . A I                             ║',
    ' ║             C Y B E R  ·  L A B  ·  C O N S O L E                ║',
    ' ║                                                                   ║',
    ' ╚═══════════════════════════════════════════════════════════════════╝',
  ];
}
async function boot() {
  for (const line of banner()) {
    console.log(paint(line, line.includes('G H O S T E R') ? 'pink' : 'cyan'));
    if (motionEnabled) await pause(45);
  }
  console.log(' ' + paint('GHOSTER.AI', 'green') + paint('  /  LOCAL-FIRST  /  PRIVATE TEST SCOPE', 'dim'));
  if (motionEnabled) {
    for (let i=0; i<=24; i+=2) {
      process.stdout.write('\r ' + paint('BOOT SEQUENCE  ', 'dim') + paint('█'.repeat(i), 'cyan') + paint('░'.repeat(24-i), 'dim') + ' ' + String(Math.round(i/24*100)).padStart(3) + '%');
      await pause(32);
    }
    process.stdout.write('\n');
  }
}
function python() {
  const choices = [[VENV, []], ...(process.platform === 'win32' ? [['py', ['-3']], ['python', []]] : [['python3', []], ['python', []]])];
  for (const [bin, prefix] of choices) {
    if (bin === VENV && !existsSync(bin)) continue;
    const check = spawnSync(bin, [...prefix, '-c', 'import sys; assert sys.version_info >= (3,10); print(sys.version.split()[0])'], {encoding:'utf8', timeout:5000, windowsHide:true});
    if (check.status === 0) return {bin, prefix, version:check.stdout.trim(), virtual:bin===VENV};
  }
  return null;
}
function hasFile(name) { return existsSync(path.join(ROOT, name)); }
function health() {
  console.log('\n' + paint('╭──[ GHOSTER.AI // SYSTEM HEALTH ]' + '─'.repeat(24), 'blue'));
  log('NODE', process.version + ' · ' + process.platform, 'green');
  const py = python();
  log('PYTHON', py ? py.version + (py.virtual ? ' (.venv)' : ' (system)') : 'Python 3.10+ tidak ditemukan', py ? 'green':'yellow');
  for (const name of ['requirements.txt', 'lab.py', 'web_lab_flow.py', 'dashboard.py'])
    log('CHECK', name + ': ' + (hasFile(name) ? 'READY' : 'MISSING'), hasFile(name) ? 'green':'yellow');
  console.log(paint('╰' + '─'.repeat(63), 'blue'));
}
async function launch(bin, args, description) {
  log('START', description, 'pink');
  const result = await new Promise(resolve => {
    const child = spawn(bin, args, {cwd:ROOT, stdio:'inherit', env:{...process.env, PYTHONUNBUFFERED:'1'}});
    let done = false;
    const finish = code => { if (!done) {done=true; resolve(code);} };
    child.once('error', error => {log('ERROR', error.message, 'red'); finish(1);});
    child.once('close', (code, signal) => finish(signal ? 130 : code ?? 1));
  });
  log(result === 0 ? 'SUCCESS' : 'FAILED', description + ' (exit ' + result + ')', result === 0 ? 'green':'red');
  return result === 0;
}
async function initialize() {
  const available = python();
  if (!available) {log('BLOCKED', 'Instal Python 3.10+ terlebih dahulu', 'red'); return;}
  if (!hasFile('requirements.txt')) {log('BLOCKED', 'requirements.txt tidak ditemukan di root repo', 'red'); return;}
  if (!existsSync(VENV)) {
    if (!await launch(available.bin, [...available.prefix, '-m','venv','.venv'], 'Membuat Python virtual environment')) return;
  } else log('VENV', 'Lingkungan .venv sudah tersedia', 'green');
  if (!existsSync(VENV)) {log('BLOCKED', 'Python .venv tidak berhasil dibuat', 'red'); return;}
  if (!await launch(VENV, ['-m','pip','install','-r','requirements.txt'], 'Memasang dependensi lab')) return;
  await launch(VENV, ['-m','playwright','install','chromium'], 'Memasang Chromium Playwright');
}
async function runner(script, args=[]) {
  if (!hasFile(script)) {log('MISSING', script + ' tidak ada di root repo', 'red'); return;}
  if (!existsSync(VENV)) {log('SETUP', 'Pilih [1] INITIALIZE terlebih dahulu', 'yellow'); return;}
  log('SCOPE', 'Satu pengujian / tanpa request otomatis ke Instagram', 'green');
  await launch(VENV, [script, ...args], 'Menjalankan ' + script);
}
async function diagnostics() {
  health();
  if (!existsSync(VENV)) {log('SETUP', 'Buat .venv untuk menjalankan tes Python', 'yellow'); return;}
  for (const script of ['tests.py', 'tests_web_lab_flow.py', 'tests_dashboard.py'])
    if (hasFile(script)) await runner(script);
}
function menu() {
  console.log('\n' + paint('╭──[ GHOSTER.AI // MAIN CONTROL ]' + '─'.repeat(27), 'blue'));
  const entries = [
    ['1','INITIALIZE','Persiapkan Python, dependensi, Chromium'],
    ['2','SESSION LAB','Simulasi keamanan sesi offline'],
    ['3','PRIVATE FLOW','Alur UI single-run pada web lab privat'],
    ['4','WEB DASHBOARD','Jalankan dashboard lokal'],
    ['5','DIAGNOSTICS','Health check dan unit tests'],
    ['0','SHUTDOWN','Tutup launcher'],
  ];
  for (const [id,title,desc] of entries)
    console.log('  ' + paint('['+id+']', 'cyan') + ' ' + paint(title.padEnd(17), 'green') + paint(desc, 'dim'));
  console.log(paint('╰' + '─'.repeat(63), 'blue'));
}
async function interactive() {
  await boot();
  health();
  while (true) {
    menu();
    const rl = createInterface({input:process.stdin, output:process.stdout});
    let choice = '';
    try { choice = (await rl.question(paint('  └─[ GHOSTER.AI / SELECT ] › ', 'pink'))).trim().toLowerCase(); }
    catch {choice = '0';}
    finally {rl.close();}
    if (choice === '0' || choice === 'exit' || choice === 'q') {log('SHUTDOWN', 'Ghoster.ai ditutup', 'green'); return;}
    if (choice === '1') await initialize();
    else if (choice === '2') await runner('lab.py');
    else if (choice === '3') await runner('web_lab_flow.py');
    else if (choice === '4') await runner('dashboard.py');
    else if (choice === '5') await diagnostics();
    else log('INVALID', 'Pilih salah satu menu 0–5', 'yellow');
  }
}
function help() {
  console.log('Ghoster.ai — Cyber Lab Terminal\n\n  npm run setup                  Jalankan menu interaktif\n  npm run setup -- --check       Diagnosis tanpa menu\n  npm run setup -- --help        Tampilkan bantuan\n  npm run setup -- --no-animation  Nonaktifkan animasi\n  npm run test:setup             Jalankan unit test\n\nNode.js 18+ dan Python 3.10+ diperlukan. Hanya untuk pengujian lab privat.');
}
async function main() {
  if (flags.has('--help') || flags.has('-h')) return help();
  if (flags.has('--check')) return health();
  if (!process.stdin.isTTY) return help();
  try {await interactive();}
  catch (err) {log('FATAL', err?.message || String(err), 'red'); process.exitCode = 1;}
}
await main();
