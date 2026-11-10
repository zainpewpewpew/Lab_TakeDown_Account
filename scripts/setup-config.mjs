import net from 'node:net';

const DENIED_DOMAINS = ['instagram.com', 'facebook.com', 'meta.com', 'threads.net', 'messenger.com'];

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
  return `Headless ${config.headless ? 'ON' : 'OFF'}   /   Proxy ${config.proxy ? 'ON' : 'OFF'}`;
}
