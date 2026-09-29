FROM golang:1.26-alpine AS build
WORKDIR /src

COPY go.mod ./
COPY cmd/ ./cmd/
COPY internal/ ./internal/
RUN CGO_ENABLED=0 go build -o /out/server ./cmd/server

FROM scratch
WORKDIR /app
COPY --from=build /out/server /app/server
COPY models/elliptic-logistic-v1/model.json /app/models/elliptic-logistic-v1/model.json
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/app/server"]
