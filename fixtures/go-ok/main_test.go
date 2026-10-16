package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func get(t *testing.T, path string) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	handler().ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
	return rec
}

func TestHealthEndpoints(t *testing.T) {
	for _, p := range []string{"/healthz", "/ready"} {
		if code := get(t, p).Code; code != http.StatusOK {
			t.Errorf("%s: got %d, want 200", p, code)
		}
	}
}

func TestRootReturnsAppName(t *testing.T) {
	rec := get(t, "/")
	var body map[string]string
	if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if body["app"] != "fixture-go" {
		t.Errorf("app = %q, want fixture-go", body["app"])
	}
}

func TestUnknownPathIs404(t *testing.T) {
	if code := get(t, "/nope").Code; code != http.StatusNotFound {
		t.Errorf("got %d, want 404", code)
	}
}
