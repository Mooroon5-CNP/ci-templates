package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
)

func handler() http.Handler {
	mux := http.NewServeMux()
	ok := func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "text/plain")
		_, _ = w.Write([]byte("ok"))
	}
	mux.HandleFunc("/healthz", ok)
	mux.HandleFunc("/ready", ok)
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{
			"app": "fixture-go", "lang": "go", "status": "running",
		})
	})
	return mux
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	log.Printf("fixture-go listening on %s", port)
	log.Fatal(http.ListenAndServe(":"+port, handler()))
}
