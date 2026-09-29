.PHONY: test build run score score-all fmt ml-test ml-train

INPUT ?= testdata/risk_examples/licit-agreement.json
TESTDATA ?= testdata/risk_examples
MODEL ?= models/elliptic-logistic-v1/model.json
LISTEN ?= :8080

test:
	go test ./...

build:
	go build -o bin/ ./cmd/server

run:
	go run ./cmd/server -listen "$(LISTEN)" -model "$(MODEL)"

score:
	go run ./cmd/server -input "$(INPUT)" -model "$(MODEL)"

score-all:
	go run ./cmd/server -input-dir "$(TESTDATA)" -model "$(MODEL)"

fmt:
	go fmt ./...

ml-test:
	python -m unittest discover -s tests -p "test_*.py"

ml-train:
	python -m ml.train
