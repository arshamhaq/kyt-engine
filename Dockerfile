FROM golang:1.26-alpine AS build
WORKDIR /src

COPY go.mod ./
COPY cmd/ ./cmd/
COPY internal/ ./internal/
RUN CGO_ENABLED=0 go build -o /out/server ./cmd/server

FROM scratch
COPY --from=build /out/server /server
USER 65532:65532
ENTRYPOINT ["/server"]
