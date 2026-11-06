'use strict';

const http = require('http');
const { logger: defaultLogger } = require('./logger');

function handler(req, res) {
    if (req.url === '/healthz' || req.url === '/ready') {
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        return res.end('ok');
    }
    if (req.url === '/') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ app: '{{APP_NAME}}', lang: 'node', status: 'running' }));
    }
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    return res.end('not found');
}

function createServer({ logger = defaultLogger } = {}) {
    return http.createServer((req, res) => {
        const start = Date.now();
        res.on('finish', () => {
            // Probes run every few seconds: keep them at DEBUG to avoid noise.
            const probe = req.url === '/healthz' || req.url === '/ready';
            logger[probe ? 'debug' : 'info']('http request', {
                method: req.method,
                path: req.url,
                status: res.statusCode,
                duration_ms: Date.now() - start,
            });
        });
        handler(req, res);
    });
}

module.exports = { createServer };
