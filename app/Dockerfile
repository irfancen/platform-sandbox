FROM python:3.13-slim-trixie@sha256:09a17cad02668ae61ece136b4fd36ac3849e14f670ebedb637ea3e15580525bc AS build

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary=:all: --target /deps -r requirements.txt

FROM gcr.io/distroless/python3-debian13:nonroot@sha256:1c32c3720dc4c7f0c7dbe998737f32c200add6511eca7cec705008be488b87d6

WORKDIR /app
COPY --from=build /deps /deps
COPY src/ .

ENV PYTHONPATH=/deps \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER 65532:65532
EXPOSE 8080

ENTRYPOINT ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-server-header"]
