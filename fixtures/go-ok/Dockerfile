FROM golang:1.22-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY *.go ./
RUN CGO_ENABLED=0 go build -o /out/server .

FROM alpine:3.20
COPY --from=build /out/server /usr/local/bin/server
USER 1000
EXPOSE 8080
ENV PORT=8080
HEALTHCHECK --interval=30s --timeout=5s CMD ["wget", "-qO-", "http://localhost:8080/healthz"]
CMD ["server"]
