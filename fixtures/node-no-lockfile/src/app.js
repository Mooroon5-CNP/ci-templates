const http = require('http');

function handler(req, res) {
  if (req.url === '/healthz' || req.url === '/ready') {
    res.writeHead(200, { 'Content-Type': 'text/plain' });
    res.end('ok');
    return;
  }
  res.writeHead(404);
  res.end('not found');
}

module.exports = { handler, server: () => http.createServer(handler) };
