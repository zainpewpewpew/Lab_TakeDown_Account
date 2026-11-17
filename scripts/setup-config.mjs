import net from 'node:net';
import dns from 'node:dns/promises';

const DENIED_DOMAINS = ['instagram.com', 'cdninstagram.com', 'facebook.com', 'fbcdn.net', 'meta.com', 'threads.net', 'messenger.com', 'whatsapp.com'];
const USERNAME_RE = /^[a-zA-Z0-9](?:[a-zA-Z0-9._]{0,28}[a-zA-Z0-9])?$/;
const DEFAULT_LAB_BASE_URL = process.env.LAB_BASE_URL || 'http://127.0.0.1:3000';

function hostDenied(host) {
  const h = String(host || '').toLowerCase().replace(/\.$/, '');
  return DENIED_DOMAINS.some(d => h === d || h.endsWith('.' + d));
}

function privateIPv4(ip) {
  if (net.isIP(ip) !== 4) return false;
  return /^(127|10|192\.168|169\.254)\./.test(ip) || /^172\.(1[6-9]|2\d|3[01])\./.test(ip);
}

function validateUsername(value) {
  const name = String(value ?? '').trim();
  if (!name) throw new Error('Username lab kosong');
  if (name.length > 30) throw new Error('Username lab melebihi 30 karakter');
  if (!USERNAME_RE.test(name)) throw new Error('Username lab hanya huruf/angka/._ (1–30)');
  return name;
}

export function labBaseUrl() {
  return DEFAULT_LAB_BASE_URL.replace(/\/+$/, '');
}

export async function resolveLabTargetFromUsername(raw, opts = {}) {
  const base = (opts.labBaseUrl || labBaseUrl()).replace(/\/+$/, '');
  const value = String(raw ?? '').trim();
  if (!value) throw new Error('Masukkan username lab');

  // Guard: jangan izinkan user menyusupkan URL Instagram/Meta lewat kolom username.
  if (/^https?:\/\//i.test(value) || value.includes('://')) {
    throw new Error('Kolom ini hanya menerima username lab; URL tidak diperbolehkan');
  }

  let user = value;
  let overrideBase = null;

  if (value.includes('@')) {
    const [left, right] = value.split('@', 2);
    user = validateUsername(left);
    const originRaw = /^https?:\/\//i.test(right) ? right : 'http://' + right;
    const originUrl = normalizedTarget(originRaw);
    const parsed = new URL(originUrl);
    const host = parsed.hostname.toLowerCase();
    let isPrivate = false;
    if (host === 'localhost' || host.endsWith('.localhost')) isPrivate = true;
    else if (privateIPv4(host)) isPrivate = true;
    else if (host.endsWith('.test') || host.endsWith('.internal') || host.endsWith('.home.arpa')) {
      try {
        const addrs = await dns.lookup(host, { all: true, family: 4 });
        isPrivate = addrs.length > 0 && addrs.every(a => privateIPv4(a.address));
      } catch { isPrivate = false; }
    }
    if (!isPrivate) throw new Error('Origin lab harus localhost / IP privat / host lab yang resolve ke IP privat');
    overrideBase = originUrl.replace(/\/+$/, '');
  } else {
    user = validateUsername(value);
  }

  const chosenBase = overrideBase || base;
  // Validasi ulang base supaya operator tidak mengarahkannya ke domain publik via env.
  const parsedBase = new URL(chosenBase);
  if (hostDenied(parsedBase.hostname)) {
    throw new Error('LAB_BASE_URL menunjuk ke domain terlarang (Meta/Instagram)');
  }

  return `${chosenBase}/u/${encodeURIComponent(user)}`;
}

export function normalizedTarget(input) {
  const value = String(input ?? '').trim();
  if (!value || value.length > 2048 || /\s/.test(value)) throw new Error('Masukkan domain atau URL yang valid');
  if (/^[a-z][\w+.-]*:\/\//i.test(value) && !/^https?:\/\//i.test(value)) {
    throw new Error('URL hanya boleh menggunakan http:// atau https://');
  }
  if (value.startsWith('//')) throw new Error('URL tanpa skema tidak valid');
  let url;
  const hasScheme = /^https?:\/\//i.test(value);
  try {
    if (hasScheme) url = new URL(value);
    else {
      const hostname = value.split(/[\/?#]/, 1)[0].split(':')[0].toLowerCase();
      const local = hostname === 'localhost' || hostname.endsWith('.localhost') || hostname.endsWith('.test') || hostname.endsWith('.internal') || hostname.endsWith('.home.arpa') ||
        (net.isIP(hostname) === 4 && (/^(127|10|192\.168|169\.254)\./.test(hostname) || /^172\.(1[6-9]|2\d|3[01])\./.test(hostname)));
      url = new URL((local ? 'http://' : 'https://') + value);
    }
  } catch {
    throw new Error('URL tidak valid. Contoh: labprivate.com atau http://127.0.0.1:3000');
  }
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.username || url.password) {
    throw new Error('URL harus http(s) tanpa kredensial di alamat');
  }
  const host = url.hostname.replace(/\.$/, '').toLowerCase();
  if (DENIED_DOMAINS.some(domain => host === domain || host.endsWith('.' + domain))) {
    throw new Error('URL layanan Instagram/Meta tidak termasuk pengujian lab');
  }
  return url.toString();
}

export function normalizedProxy(input) {
  const value = String(input ?? '').trim();
  if (!value || /\s/.test(value) || value.length > 1024) throw new Error('Masukkan URL proxy yang valid');
  let url;
  try {url = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(value) ? value : 'http://' + value);} catch {
    throw new Error('Format proxy tidak valid; gunakan host:port atau http://host:port');
  }
  if (!['http:', 'socks5:'].includes(url.protocol) || !url.hostname || !url.port || !['', '/'].includes(url.pathname) || url.search || url.hash) {
    throw new Error('Proxy harus http://host:port atau socks5://host:port');
  }
  const port = Number(url.port);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Port proxy tidak valid');
  return {
    server: `${url.protocol}//${url.host}`,
    username: decodeURIComponent(url.username),
    password: decodeURIComponent(url.password),
    label: `${url.protocol}//${url.host}`,
  };
}

export function configLabel(config) {
  return `Headless ${config.headless ? 'ON' : 'OFF'}   /   Proxy ${config.proxy ? 'ON' : 'OFF'}   /   Base ${labBaseUrl()}`;
}
