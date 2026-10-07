# Stage this base image and wheelhouse on the approved build host first.
FROM python:3.12-slim AS runtime
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /opt/review-assistant
COPY wheelhouse /wheelhouse
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-index --find-links=/wheelhouse --no-build-isolation . && rm -rf /wheelhouse
RUN useradd --uid 10001 --create-home reviewer && mkdir /data && chown reviewer /data
USER reviewer
CMD ["python", "-m", "app.server", "--reviewer", "local-reviewer", "--data-dir", "/data"]

FROM runtime AS verify
USER root
COPY wheelhouse /wheelhouse
RUN pip install --no-index --find-links=/wheelhouse pytest==9.1.0 && rm -rf /wheelhouse
COPY tests ./tests
COPY evaluation ./evaluation
USER reviewer
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
