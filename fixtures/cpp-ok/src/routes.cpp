#include "routes.hpp"

Response route(const std::string& path) {
    if (path == "/healthz" || path == "/ready") {
        return {200, "text/plain", "ok"};
    }
    if (path == "/") {
        return {200, "application/json",
                R"({"app":"fixture-cpp","lang":"cpp","status":"running"})"};
    }
    return {404, "text/plain", "not found"};
}
