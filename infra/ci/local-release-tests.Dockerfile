# Reuse production dependency installation and the integrity-checked verifier.
FROM atlas-ci-local-release-api

USER 0:0
RUN python -m pip install --no-cache-dir pytest==8.4.1 httpx==0.28.1 psutil==7.2.2
COPY . /workspace
# .dockerignore excludes host verifier binaries. Retain the image's locked one.
RUN cp -a /app/app/attestation/bin /workspace/apps/api/app/attestation/bin
ENV PYTHONPATH=/workspace/apps/runtime/ansible
WORKDIR /workspace/apps/api
ENTRYPOINT ["python", "/workspace/infra/ci/run-local-release-tests.py"]
