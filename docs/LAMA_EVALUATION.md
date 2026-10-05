# LaMa packaging evaluation

Status: deferred as a distributable backend.

## What was verified

- The official LaMa source repository includes an Apache License 2.0 file: <https://github.com/advimman/lama/blob/main/LICENSE>.
- The official README downloads pretrained checkpoints separately from Google Drive or a third-party Hugging Face mirror rather than storing them in the licensed source tree: <https://github.com/advimman/lama/blob/main/README.md#inference>.
- The official setup still documents PyTorch 1.8.0, torchvision 0.9.0, CUDA 10.2 and pytorch-lightning 1.2.9. Its requirements also pin older packages such as scikit-image 0.17.2 and scikit-learn 0.24.2: <https://github.com/advimman/lama/blob/main/requirements.txt>.
- As of 2026-09-28, an upstream issue asking whether the separately distributed pretrained weights inherit the source-code license remains open and has no maintainer clarification: <https://github.com/advimman/lama/issues/366>.

The source-code license is clear. The evidence currently available does not establish an explicit license for the separately hosted Big-LaMa checkpoint. A license label on a third-party mirror is not treated as permission from the original model publisher.

## Decision

Do not bundle, auto-download or advertise the Big-LaMa checkpoint in the current open-source release. Keep OpenCV Telea as the dependency-light executable baseline and require visual review on structured or textured regions.

This is an engineering distribution decision, not legal advice. It can be revisited when the original publisher provides a checkpoint license or when the project selects a different model with an authoritative license and compatible runtime.

## Requirements for a future model adapter

1. Record the authoritative model URL, exact license text, file size and SHA-256 before adding code.
2. Keep model dependencies optional and isolated from the Python 3.12 API environment.
3. Never download weights without an explicit user action and a visible size/license notice.
4. Run the same generated benchmark corpus and record wall time, peak memory and quality metrics.
5. Preserve the existing guarantees: new output artifact, fixed dimensions, successful decode and zero pixel changes outside the mask.
6. Add CPU and Apple Silicon validation before exposing the adapter in capabilities.
