#!/usr/bin/env node
/** Launch Ghoster.ai local dashboard using the existing Python virtual environment. */
import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import process from 'node:process';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const VENV=path.join(ROOT,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const python=existsSync(VENV)?VENV:(process.platform==='win32'?'py':'python3');
const args=(process.platform==='win32'&&!existsSync(VENV)?['-3']:[]).concat(['dashboard.py',...process.argv.slice(2)]);
console.log('\x1b[36m◆ GHOSTER.AI // WEB CONTROL\x1b[0m');
console.log('  Starting loopback-only dashboard: http://127.0.0.1:8787/');
console.log('  Press CTRL+C to stop.\n');
const child=spawn(python,args,{cwd:ROOT,stdio:'inherit',env:{...process.env,PYTHONUNBUFFERED:'1'}});
for(const sig of ['SIGINT','SIGTERM']) process.on(sig,()=>{if(child.pid)child.kill(sig)});
child.on('error',error=>{console.error('Python runner unavailable:',error.message);process.exitCode=1});
child.on('close',(code,signal)=>{if(!process.exitCode)process.exitCode=signal?130:(code??1)});
