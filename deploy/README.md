# Offline deployment

Prepare and license-review dependencies/weights on an authorized staging host with no proposals. Use a platform/Python version matching the target. Resolve and archive exact transitive versions and hashes as part of that staging process; the optional model dependency ranges are not a reviewed lockfile.

Example on a matching Linux/Python 3.12 staging host:

```sh
python -m pip download --dest wheelhouse 'pdfplumber==0.11.9' 'pytest==9.1.0' 'setuptools>=77' wheel
docker pull python:3.12-slim
docker build --network none -f deploy/Dockerfile --target verify -t review-assistant-verify .
docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --memory 2g --cpus 2 --cap-drop ALL --security-opt no-new-privileges review-assistant-verify
```

This verification container has no external network, but loopback remains available for the HTTP integration tests. It runs the PDF-to-confirmed-assessment test and egress denial test without model weights. Supply staged optional model runtimes/weights and repeat with real candidates before approval. The supplied Docker recipe was authored but may need target-specific wheel or accelerator libraries; do not treat it as deployment verification until built and run on the target.

The runtime deliberately binds only to loopback. Docker `--network none` therefore **does not expose a host browser UI**, and publishing a port does not change that. Use the native service in an approved workstation/VM with outbound traffic blocked, or place the browser in the same isolated desktop/VM network namespace. Do not solve this by exposing the unaudited development server on a public interface. A production reverse proxy/multi-user deployment needs a separate access-control design.

For the native service, prepare a venv/wheelhouse, then install with `pip --no-index --find-links ...` and run with `--data-dir` on an encrypted, access-controlled local volume. Do not place proposal storage on cloud-synced directories. Configure approved OS firewall/VM isolation for both Python and any native model server. The Python audit hook is defense in depth, not a sandbox for arbitrary C/CUDA/ROCm extensions or subprocesses.

Stage each model artifact together with a SHA-256 manifest, upstream source revision, tokenizer, license and approved runtime package versions. Pass the manifest fingerprint as `--model-version`; the application records it but does not attest the correctness of an administrator-supplied fingerprint. OpenJev custom runtime code must be reviewed separately. Disable upstream caches containing proposal states (for jevos, `--state-cache 0`) or include their lifetime in the retention policy.

Run `python -m app.server --reviewer ID --data-dir /approved/reviews --purge-only` under an approved OS scheduler when the service is stopped. Retention defaults must be approved before confidential use. Include audit notes, exported files, backups, snapshots and private evaluation datasets in the policy. No container build or default test contains actual proposal data.
