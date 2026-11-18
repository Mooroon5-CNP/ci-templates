'use strict';

const test = require('node:test');
const assert = require('node:assert');
const { renderPage } = require('../src/render');

test('page contains title and api placeholder', () => {
    const html = renderPage('demo');
    assert.match(html, /<h1>demo<\/h1>/);
    assert.match(html, /\/api\/info/);
});
