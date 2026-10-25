const { server } = require('./app');

server().listen(process.env.PORT || 8080);
