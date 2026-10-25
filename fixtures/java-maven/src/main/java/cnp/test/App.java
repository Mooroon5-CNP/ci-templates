package cnp.test;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;

public final class App {

    /** Status, content type and body for a GET on {@code path}. */
    public record Response(int status, String contentType, String body) { }

    private App() { }

    public static Response route(String path) {
        if (path.equals("/healthz") || path.equals("/ready")) {
            return new Response(200, "text/plain", "ok");
        }
        if (path.equals("/")) {
            return new Response(200, "application/json",
                "{\"app\":\"fixture-java\",\"lang\":\"java\",\"status\":\"running\"}");
        }
        return new Response(404, "text/plain", "not found");
    }

    public static void main(String[] args) throws IOException {
        int port = Integer.parseInt(System.getenv().getOrDefault("PORT", "8080"));
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/", exchange -> {
            Response r = route(exchange.getRequestURI().getPath());
            byte[] bytes = r.body().getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().set("Content-Type", r.contentType());
            exchange.sendResponseHeaders(r.status(), bytes.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(bytes);
            }
        });
        System.out.println("fixture-java listening on " + port);
        server.start();
    }
}
