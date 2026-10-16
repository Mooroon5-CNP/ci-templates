FROM alpine:3.20 AS build
# hadolint ignore=DL3018
RUN apk add --no-cache g++ cmake make
WORKDIR /src
COPY CMakeLists.txt ./
COPY src/ ./src/
COPY tests/ ./tests/
RUN cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --target server

FROM alpine:3.20
# hadolint ignore=DL3018
RUN apk add --no-cache libstdc++
COPY --from=build /src/build/server /usr/local/bin/server
USER 1000
EXPOSE 8080
ENV PORT=8080
HEALTHCHECK --interval=30s --timeout=5s CMD ["wget", "-qO-", "http://localhost:8080/healthz"]
CMD ["server"]
