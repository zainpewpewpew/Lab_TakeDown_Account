"""Single-process local mock recovery site; no external endpoints."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recovery Flow Testbed // OFFLINE</title>
<style>
:root{color-scheme:dark;font:15px ui-monospace,SFMono-Regular,Menlo,monospace;background:#040b10;color:#c7fee5}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(ellipse at top right,#113a3a77,transparent 45%),repeating-linear-gradient(90deg,#0b241b25 0 1px,transparent 1px 48px)}
header{padding:25px 6vw;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #144e3a}
.logo{letter-spacing:.22em;color:#36fbaa;font-weight:700}.chip{border:1px solid #2cee9b;padding:7px 12px;color:#2cee9b;font-size:.72rem;letter-spacing:.09em}
main{max-width:760px;margin:7vh auto;padding:20px}.card{padding:42px 38px;border:1px solid #2eee9d55;border-radius:14px;box-shadow:0 0 55px #20e4ac10;background:#07181eec}
h1{font-size:clamp(24px,4vw,40px);letter-spacing:-.06em;margin:8px 0 24px}.eyebrow{color:#31e99b;font-size:.7rem;letter-spacing:.25em}
p{line-height:1.8;color:#8cb9ad}a{color:#43ffd2;text-decoration:none}
input[type=text]{padding:15px;background:#031114;border:1px solid #268264;color:#ddfff1;border-radius:8px;width:100%;outline:0;font:inherit}
button,.button{display:inline-block;font:inherit;color:#05160d;border:0;border-radius:8px;padding:14px 20px;background:#4df7aa;cursor:pointer;margin:20px 0}
.option{display:block;padding:14px;margin:13px 0;border:1px solid #226453;border-radius:8px;cursor:pointer}.option input{accent-color:#4df7aa}
.hidden{display:none}.status{color:#c2ffdb;padding:16px;border:1px solid #2cee9b77;border-radius:9px;overflow-wrap:anywhere}
footer{text-align:center;color:#6a9984;font-size:.73rem;margin:40px auto}
</style></head><body><header><div class="logo">RECOVERY // TESTBED</div><span class="chip">PRIVATE LOCAL SIMULATOR</span></header>
<main><section class="card"><div class="eyebrow">OFFLINE AUTHENTICATION FLOW</div>
<h1 id="heading">Security recovery test</h1>
<div id="login"><p>Test user recovery options in a controlled lab. This interface does not connect to Instagram.</p>
<a href="/accounts/password/reset/" role="link"><div role="none"><span>Forgot password?</span></div></a></div>
<div id="form" class="hidden"><p>Username, email or phone (dummy test account)</p>
<input type="text" id="_r_s_" autocomplete="off" placeholder="Username, email or phone">
<button type="button" id="first-continue" onclick="firstContinue()"><div role="none"><span>Continue</span></div></button></div>
<div id="options" class="hidden"><p>Choose a recovery channel.</p>
<div id="option-email"><label class="option"><input type="radio" name="channel" value="email"><div>Get link via email</div></label></div>
<div id="option-sms"><label class="option"><input type="radio" name="channel" value="sms"><div>Get link via SMS</div></label></div>
<button id="second-continue" onclick="secondContinue()"><div role="none"><span>Continue</span></div></button></div>
<div id="human" class="hidden"><span>Help us confirm it's you</span>
<p>This is a mock manual check. Click the completion button yourself in this browser, then press Enter in your terminal.</p>
<button id="manual-confirm" onclick="finish()">I completed verification</button></div>
<div id="success" class="hidden"><p class="status" id="message"></p><button id="okay" onclick="done()"><span>OK</span></button></div>
<div id="complete" class="hidden"><p class="status">Done — simulated recovery request recorded locally.</p></div>
</section></main><footer>NO REAL EMAIL OR SMS WILL BE SENT · LAB DEMO ONLY</footer>
<script>
const opts=__OPTIONS__, challenge=__CHALLENGE__; let selectedChannel="email";
const $=id=>document.getElementById(id);
function show(id){for(const name of ['login','form','options','human','success','complete'])$(name).classList.toggle('hidden', name!==id)}
function initialize(){if(location.pathname==='/accounts/password/reset/')show('form'); else show('login')}
function firstContinue(){if(!$('_r_s_').value.trim()){alert('Enter an identifier');return}
if(opts==='email')$('option-sms').remove();if(opts==='sms')$('option-email').remove();
if(opts==='none'){$('option-email').remove();$('option-sms').remove()}
show('options');$('heading').textContent='Choose recovery method'}
function secondContinue(){const checked=document.querySelector('input[name=channel]:checked');if(!checked){alert('Select a recovery method');return}selectedChannel=checked.value;
if(challenge){show('human');$('heading').textContent='Manual verification'}else finish()}
function finish(){let channel=selectedChannel;
$('message').textContent=channel==='email'?'We sent an email to d*******o@lab.test with a link to get back into your account.':'We texted a password reset link to +62*********23. Tap on the link to reset your password.';
$('heading').textContent='Request completed';show('success')}
function done(){show('complete')}
initialize();
</script></body></html>'''


def start_mock_server(options="both", challenge=False):
    if options not in {"both", "email", "sms", "none"}:
        raise ValueError("Invalid mock options")
    html = HTML.replace("__OPTIONS__", json.dumps(options)).replace("__CHALLENGE__", json.dumps(bool(challenge)))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path not in {"/", "/accounts/password/reset/"}:
                self.send_error(404)
                return
            payload = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"