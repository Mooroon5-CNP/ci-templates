#pragma once

#include <string>

struct Response {
    int status;
    std::string content_type;
    std::string body;
};

Response route(const std::string& path);
