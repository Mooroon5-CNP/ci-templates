'use strict';

const fs = require('fs');
const path = require('path');
const { renderPage } = require('./render');

const out = path.join(__dirname, '..', 'dist');
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, 'index.html'), renderPage('{{APP_NAME}}'));
console.log(`built ${out}/index.html`);
