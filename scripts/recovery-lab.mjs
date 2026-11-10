#!/usr/bin/env node
/** Ghoster.ai one-shot private recovery lab runner (Chromium / Multilogin). */
import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import process from 'node:process';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const venv=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const bin=existsSync(venv)?venv:(process.platform==='win32'?'py':'python3');
const raw=process.argv.slice(2);
const multilogin=raw.includes('--multilogin');
const remaining=raw.filter(arg=>arg!=='--multilogin');
const prefix=process.platform==='win32'&&!existsSync(venv)?['-3']:[];
const args=[...prefix,'-u','recovery_lab_cli.py','--browser-mode',multilogin?'multilogin':'chromium',...remaining];
console.log('\x1b[36m╔══════════════════════════════════════════════════╗');
console.log('║     G H O S T E R . A I  //  LAB CONTROL      ║');
console.log('╚══════════════════════════════════════════════════╝\x1b[0m');
console.log('MODE: '+(multilogin?'MULTILOGIN CDP':'LOCAL CHROMIUM')+'  ·  ONE SHOT  ·  PRIVATE LAB ONLY');
const worker=spawn(bin,args,{cwd:root,stdio:'inherit',env:{...process.env,PYTHONUNBUFFERED:'1'}});
worker.once('error',err=>{console.error('[ERROR] Python tidak dapat dijalankan:',err.message);process.exitCode=1;});
worker.once('close',(code,signal)=>{if(!process.exitCode)process.exitCode=signal?130:(code??1);});
