const test = require('node:test');
const assert = require('node:assert');
const http = require('http');
const { server } = require('../src/app');

test('/healthz answers ok', async () => {
  const s = server().listen(0);
  const { port } = s.address();
  const body = await new Promise((resolve) => {
    http.get({ port, path: '/healthz' }, (res) => {
      let data = '';
      res.on('data', (c) => (data += c));
      res.on('end', () => resolve(data));
    });
  });
  s.close();
  assert.strictEqual(body, 'ok');
});
