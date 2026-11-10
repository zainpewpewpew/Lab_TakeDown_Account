#!/usr/bin/env node
/** Ghoster.ai — local/private lab terminal control. No third-party automation. */
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { createInterface } from 'node:readline/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import process from 'node:process';
import { normalizedTarget, normalizedProxy, configLabel } from './setup-config.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const VENV = path.join(ROOT, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const flags = new Set(process.argv.slice(2));
const colorEnabled = Boolean(process.stdout.isTTY && process.env.NO_COLOR === undefined && process.env.TERM !== 'dumb');
const motionEnabled = colorEnabled && process.env.REDUCED_MOTION !== '1' && !process.env.CI && !flags.has('--no-animation');
const colors = { cyan:'\x1b[38;2;52;229;247m', pink:'\x1b[38;2;255;92;207m', green:'\x1b[38;2;113;250;178m', blue:'\x1b[38;2;120;157;255m', yellow:'\x1b[38;2;255;201;110m', red:'\x1b[38;2;255;108;136m', dim:'\x1b[38;2;151;164;185m' };
const paint = (s, c) => colorEnabled ? (colors[c] || '') + s + '\x1b[0m' : s;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const time = () => new Date().toLocaleTimeString('en-GB', {hour12: false});
const config = {headless:false, proxy:false};
let count = 0;
function log(stage, message, tone='cyan') {
  console.log(paint(time(), 'dim') + ' ' + paint('[' + String(++count).padStart(2, '0') + ']', 'dim') + ' ' + paint(('◆ ' + stage).padEnd(17), tone) + ' ' + message);
}
function banner() {
  return [
    ' ╔═══════════════════════════════════════════════════════════════════╗',
    ' ║                                                                   ║',
    ' ║                   G H O S T E R . A I                             ║',
    ' ║             C Y B E R  /  T E R M I N A L                ║',
    ' ║                                                                   ║',
    ' ╚═══════════════════════════════════════════════════════════════════╝',
  ];
}
function panel(title) {
  console.log('\n' + paint('╭──[ GHOSTER.AI // ' + title + ' ]' + '─'.repeat(Math.max(0, 30 - title.length)), 'blue'));
}
async function pulse(label) {
  if (!motionEnabled) return;
  const frames = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧'];
  for (const frame of frames) {
    process.stdout.write('\r ' + paint(frame + ' ' + label, 'cyan'));
    await pause(48);
  }
  process.stdout.write('\r' + ' '.repeat(label.length+8) + '\r');
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
async function launch(bin, args, description, extraEnv={}) {
  log('START', description, 'pink');
  const result = await new Promise(resolve => {
    const env = {...process.env, PYTHONUNBUFFERED:'1', ...extraEnv};
    if (!config.proxy) for (const key of ['LAB_PROXY_SERVER','LAB_PROXY_USERNAME','LAB_PROXY_PASSWORD']) delete env[key];
    const child = spawn(bin, args, {cwd:ROOT, stdio:'inherit', env});
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

async function ensureEnvironment() {
  if (existsSync(VENV)) return true;
  log('ENV', 'Persiapan otomatis Python dan Chromium', 'yellow');
  const available = python();
  if (!available) {log('BLOCKED', 'Python 3.10+ belum terpasang', 'red'); return false;}
  if (!await launch(available.bin, [...available.prefix, '-m', 'venv', '.venv'], 'Membuat .venv')) return false;
  if (!await launch(VENV, ['-m','pip','install','-r','requirements.txt'], 'Memasang Playwright')) return false;
  return await launch(VENV, ['-m','playwright','install','chromium'], 'Memasang Chromium Playwright');
}
async function ask(prompt) {
  const rl=createInterface({input:process.stdin,output:process.stdout});
  try{return (await rl.question(paint(prompt,'pink'))).trim();}
  finally{rl.close();}
}
function menu() {
  panel('MAIN CONTROL');
  const entries=[
    ['1','URL TARGET','Buka URL web lab pribadi'],
    ['2','CONFIG',configLabel(config)],
    ['0','EXIT','Tutup Ghoster.ai'],
  ];
  for(const [key,name,description] of entries)
    console.log('  '+paint('['+key+']','cyan')+' '+paint(name.padEnd(17),'green')+paint(description,'dim'));
  console.log(paint('╰'+'─'.repeat(63),'blue'));
}
function configMenu() {
  panel('CONFIG');
  for(const [key,name,enabled] of [['1','HEADLESS',config.headless],['2','PROXY',config.proxy]]) {
    console.log('  '+paint('['+key+']','cyan')+' '+paint(name.padEnd(17),'green')+paint(enabled?'ON':'OFF', enabled?'green':'yellow'));
  }
  console.log('  '+paint('[0]','cyan')+' '+paint('BACK'.padEnd(17),'dim')+'Kembali ke main menu');
  console.log(paint('╰'+'─'.repeat(63),'blue'));
}
async function runTarget() {
  const raw=await ask('  └─[ GHOSTER.AI / URL TARGET ] › ');
  let url;
  try{url=normalizedTarget(raw);}
  catch(e){log('INVALID URL',e.message,'red');return;}
  log('TARGET',url);
  const identifier=await ask('  └─[ GHOSTER.AI / USERNAME-EMAIL-PHONE ] › ');
  if(!identifier || identifier.length>128 || /[\r\n]/.test(identifier)){
    log('INVALID','Identifier dummy wajib diisi (maksimal 128 karakter)','red');return;
  }
  let proxy=null;
  if(config.proxy) {
    const entered=await ask('  └─[ GHOSTER.AI / PROXY URL ] › ');
    try{proxy=normalizedProxy(entered);}
    catch(e){log('INVALID PROXY',e.message,'red');return;}
    log('PROXY','ON · '+proxy.label,'green');
  } else log('PROXY','OFF · koneksi normal','dim');
  log('HEADLESS',config.headless?'ON':'OFF',config.headless?'yellow':'green');
  log('SCOPE','Lab privat: automation satu kali · domain publik: inspect only','yellow');
  await pulse('VERIFYING ENVIRONMENT');
  if(!hasFile('web_lab_flow.py') || !hasFile('requirements.txt')){
    log('MISSING','File Python lab tidak ditemukan','red');return;
  }
  if(!await ensureEnvironment()) return;
  const opts=['web_lab_flow.py','--url',url,'--output','output'];
  if(config.headless) opts.push('--headless');
  const env={LAB_TEST_IDENTIFIER:identifier};
  if(proxy) {
    env.LAB_PROXY_SERVER=proxy.server;
    env.LAB_PROXY_USERNAME=proxy.username;
    env.LAB_PROXY_PASSWORD=proxy.password;
  }
  await launch(VENV,opts,'Menjalankan PRIVATE LAB FLOW',env);
}
async function interactive() {
  await boot();
  log('NODE',process.version+' · '+process.platform,'green');
  while(true) {
    menu();
    const choice=await ask('  └─[ GHOSTER.AI / SELECT ] › ');
    if(['0','exit','q'].includes(choice.toLowerCase())) {
      log('SHUTDOWN','Ghoster.ai ditutup','green');return;
    }
    if(choice==='1') await runTarget();
    else if(choice==='2') {
      while(true) {
        configMenu();
        const selected=await ask('  └─[ GHOSTER.AI / CONFIG ] › ');
        if(selected==='0') break;
        if(selected==='1') {config.headless=!config.headless;log('HEADLESS',config.headless?'ON':'OFF','green');}
        else if(selected==='2') {config.proxy=!config.proxy;log('PROXY',config.proxy?'ON':'OFF','green');}
        else log('INVALID','Pilih 1, 2, atau 0','yellow');
      }
    } else log('INVALID','Pilih 1, 2, atau 0','yellow');
  }
}
function help() {
  console.log('Ghoster.ai — Cyber Terminal\n\n  npm run setup                    Main menu 1 URL TARGET / 2 CONFIG / 0 EXIT\n  npm run setup -- --check         Health check\n  npm run setup -- --preview       Lihat menu tanpa interaksi\n  npm run setup -- --no-animation  Kurangi animasi\n  npm run test:setup               Jalankan tes\n\nURL domain otomatis diberi https://. Pengujian otomatis hanya di lab privat.');
}
async function main() {
  if(flags.has('--help')||flags.has('-h')) return help();
  if(flags.has('--check')) return health();
  if(flags.has('--preview')) {await boot();menu();configMenu();return;}
  if(!process.stdin.isTTY) return help();
  try{await interactive();}
  catch(err){log('FATAL',err?.message||String(err),'red');process.exitCode=1;}
}
await main();
