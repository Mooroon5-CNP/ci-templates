'use strict';

const { createServer } = require('./app');
const { logger } = require('./logger');

const port = parseInt(process.env.PORT, 10) || {{APP_PORT}};
createServer().listen(port, () => {
    logger.info('{{APP_NAME}} listening', { port });
});
