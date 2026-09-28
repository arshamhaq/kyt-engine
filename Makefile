.PHONY: test build run fmt ml-test ml-train

test:
	go test ./...

build:
	go build -o bin/ ./cmd/server

run:
	go run ./cmd/server

fmt:
	go fmt ./...

ml-test:
	python -m unittest discover -s tests -p "test_*.py"

ml-train:
	python -m ml.train
