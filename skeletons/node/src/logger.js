'use strict';

// Structured JSON logger (one JSON object per line on stdout), picked up by the
// Datadog agent. service/env/version come from the unified service tags
// injected by the platform (DD_SERVICE, DD_ENV, DD_VERSION).

const LEVELS = { DEBUG: 10, INFO: 20, WARN: 30, ERROR: 40 };

function createLogger({ env = process.env, write = line => process.stdout.write(line + '\n') } = {}) {
    const threshold = LEVELS[String(env.LOG_LEVEL || 'INFO').toUpperCase()] || LEVELS.INFO;
    const base = {
        service: env.DD_SERVICE || '{{APP_NAME}}',
        env: env.DD_ENV || 'local',
        version: env.DD_VERSION || 'dev',
    };

    function log(level, message, fields = {}) {
        if (LEVELS[level] < threshold) return;
        write(JSON.stringify({ timestamp: new Date().toISOString(), level, message, ...base, ...fields }));
    }

    return {
        debug: (msg, fields) => log('DEBUG', msg, fields),
        info: (msg, fields) => log('INFO', msg, fields),
        warn: (msg, fields) => log('WARN', msg, fields),
        error: (msg, fields) => log('ERROR', msg, fields),
    };
}

module.exports = { createLogger, logger: createLogger() };
