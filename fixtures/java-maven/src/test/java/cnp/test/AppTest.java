package cnp.test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class AppTest {

    @Test
    void healthEndpoints() {
        assertEquals(200, App.route("/healthz").status());
        assertEquals(200, App.route("/ready").status());
    }

    @Test
    void rootReturnsAppName() {
        App.Response r = App.route("/");
        assertEquals(200, r.status());
        assertTrue(r.body().contains("\"app\":\"fixture-java\""));
    }

    @Test
    void unknownPathIs404() {
        assertEquals(404, App.route("/nope").status());
    }
}
