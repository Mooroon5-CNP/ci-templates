// Minimal single-threaded HTTP/1.0 server: enough for health checks and the
// root JSON, with no third-party dependency.
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>

#include "routes.hpp"

namespace {

std::string request_path(const std::string& request) {
    std::istringstream in(request);
    std::string method;
    std::string path;
    in >> method >> path;
    return path.empty() ? "/" : path;
}

const char* status_text(int status) {
    return status == 200 ? "OK" : "Not Found";
}

}  // namespace

int main() {
    const char* env_port = std::getenv("PORT");
    const int port = env_port ? std::atoi(env_port) : 8080;

    const int fd = socket(AF_INET, SOCK_STREAM, 0);
    const int yes = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof yes);

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(static_cast<uint16_t>(port));
    if (bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof addr) < 0 || listen(fd, 16) < 0) {
        std::perror("bind/listen");
        return 1;
    }
    std::cout << "fixture-cpp listening on " << port << std::endl;

    for (;;) {
        const int client = accept(fd, nullptr, nullptr);
        if (client < 0) {
            continue;
        }
        char buf[4096];
        const ssize_t n = read(client, buf, sizeof buf - 1);
        const Response r = route(request_path(std::string(buf, n > 0 ? static_cast<size_t>(n) : 0)));
        std::ostringstream out;
        out << "HTTP/1.0 " << r.status << " " << status_text(r.status) << "\r\n"
            << "Content-Type: " << r.content_type << "\r\n"
            << "Content-Length: " << r.body.size() << "\r\n\r\n"
            << r.body;
        const std::string s = out.str();
        if (write(client, s.data(), s.size()) < 0) {
            std::perror("write");
        }
        close(client);
    }
}
