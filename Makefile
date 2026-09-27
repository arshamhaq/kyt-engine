.PHONY: test build run fmt

test:
	go test ./...

build:
	go build -o bin/ ./cmd/server

run:
	go run ./cmd/server

fmt:
	go fmt ./...
