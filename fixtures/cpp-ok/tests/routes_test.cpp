#include <iostream>

#include "routes.hpp"

namespace {

int failures = 0;

void check(bool ok, const char* what) {
    if (!ok) {
        std::cerr << "FAIL: " << what << "\n";
        ++failures;
    }
}

}  // namespace

int main() {
    check(route("/healthz").status == 200, "/healthz is 200");
    check(route("/ready").status == 200, "/ready is 200");
    check(route("/").body.find("\"app\":\"fixture-cpp\"") != std::string::npos, "/ returns app name");
    check(route("/nope").status == 404, "unknown path is 404");
    if (failures == 0) {
        std::cout << "all route tests passed\n";
    }
    return failures == 0 ? 0 : 1;
}
