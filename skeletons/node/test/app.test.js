'use strict';

const test = require('node:test');
const assert = require('node:assert');
const { createServer } = require('../src/app');

function get(server, path) {
    const { port } = server.address();
    return fetch(`http://127.0.0.1:${port}${path}`);
}

test('health and root endpoints', async () => {
    const server = createServer().listen(0);
    try {
        assert.strictEqual((await get(server, '/healthz')).status, 200);
        assert.strictEqual((await get(server, '/ready')).status, 200);
        const body = await (await get(server, '/')).json();
        assert.strictEqual(body.app, '{{APP_NAME}}');
        assert.strictEqual((await get(server, '/nope')).status, 404);
    } finally {
        server.close();
    }
});

test('emits structured JSON logs with the Datadog unified service tags', async () => {
    const { createLogger } = require('../src/logger');
    const lines = [];
    const logger = createLogger({
        env: { DD_SERVICE: '{{APP_NAME}}', DD_ENV: 'dev', DD_VERSION: 'abc123', LOG_LEVEL: 'INFO' },
        write: line => lines.push(line),
    });
    const server = createServer({ logger }).listen(0);
    try {
        await get(server, '/');
        await get(server, '/healthz'); // DEBUG, filtered out at INFO
        await new Promise(r => setImmediate(r));
    } finally {
        server.close();
    }
    assert.strictEqual(lines.length, 1);
    const entry = JSON.parse(lines[0]);
    assert.strictEqual(entry.level, 'INFO');
    assert.strictEqual(entry.service, '{{APP_NAME}}');
    assert.strictEqual(entry.env, 'dev');
    assert.strictEqual(entry.version, 'abc123');
    assert.strictEqual(entry.path, '/');
    assert.strictEqual(entry.status, 200);
});
