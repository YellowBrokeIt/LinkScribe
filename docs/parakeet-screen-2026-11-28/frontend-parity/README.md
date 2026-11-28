# Published frontend version comparison

**All eight full-input comparisons fail the predeclared numerical parity rule.**
This identifies a difference between two published frontend implementations; it
does not identify either implementation as the correct training/export frontend
or establish an ASR quality fix.

The original int8 screen used the ordinary NumPy frontend in `onnx-asr==0.12.0`.
The coordinator then authorized this small, separate computation to compare it
with the older `nemo128.onnx` distributed alongside the pinned model weights.
No speech encoder or decoder was initialized and no speech recognition ran.

## Frozen scope and actual result

The [plan](plan.json) was frozen before computation with SHA-256
`52a9ca579d96d8cb8d496925ce0917e0028135d04c212884aaa08667954b32c1`.
The [helper](run_frontend_parity.py) has SHA-256
`d0e323ac001b23fe909f6100a25aa386af3bd46e6f8baf7ad7e8dcb63f901b93`.
It used the exact eight retained full arrays, one attempt through each frontend,
one CPU core, one ONNX thread, a 768 MiB RSS bound and a 60-second total bound.

Tolerance was taken unchanged from the pinned release's
[NeMo preprocessing test](https://github.com/istupakov/onnx-asr/blob/b9e0ce0ae3223b3d24ce5a22a5e701a726ca35fc/tests/preprocessors/test_nemo.py):
`atol=5e-4`, `rtol=1e-4`, with matching shapes and valid lengths. Every feature
value was compared; there was no cropping, edge exclusion, audio change, VAD,
dither, new installation or new model download. The release test compares its
current bundled frontend against NeMo; this experiment deliberately checks the
older model-supplied frontend, so that test does not certify these two versions
as equivalent.

The [raw report](results/report.json) and [controller record](results/execution.json)
show completion in **1.0075 seconds**, exit 0, with a sampled worker RSS peak of
**121,602,048 bytes**. The worker recorded a separate `ru_maxrss` peak of
89,587,712 bytes; these measurement APIs differ, and both are retained. No limit
was reached. The only constructed ONNX session was the exact supplied frontend
with SHA-256
`a9fde1486ebfcc08f328d75ad4610c67835fea58c73ba57e3209a6f6cf019e9f`.

| Case | NumPy valid frames | Supplied ONNX valid frames | Max absolute difference | Mean absolute difference |
|---|---:|---:|---:|---:|
| Greek 1528 | 666 | 667 | 1.464479 | 0.002326 |
| Greek 1515 | 600 | 601 | 1.658573 | 0.002695 |
| Greek 1577 | 420 | 421 | 1.518983 | 0.005210 |
| Greek 1598 | 696 | 697 | 1.685988 | 0.003304 |
| Greek 1590 | 1002 | 1003 | 1.639182 | 0.002403 |
| English 1548 | 654 | 655 | 2.733894 | 0.002217 |
| English 1510 | 792 | 793 | 2.649491 | 0.004328 |
| English 1578 | 414 | 415 | 0.987472 | 0.002253 |

Each NumPy feature hash exactly matches the feature hash captured in the
original recognition screen. The supplied ONNX graph reports `floor(N/160)+1`
valid frames; the NumPy frontend reports `floor(N/160)` and masks the final
feature frame. Their normalization also differs over shared valid frames. The
independent reviewer counted **591,058 tolerance violations inside those shared
frames**, so the difference is not confined to the final masked frame.

Every complete pair of feature arrays is retained as an `.npz` file beside the
report, with hashes recorded there. These pairs permit reconstruction of every
numerical difference. [Retained-feature analysis](retained-feature-analysis.json)
and the [independent review](../independent-review/frontend-parity-review.json)
were computed from those saved arrays without another frontend execution.

## Version history explains the difference, not its quality effect

The maintainer's
[25 November 2025 change](https://github.com/istupakov/onnx-asr/commit/726dd55a74a6223abd333810b2ddc6438e8fe2a0)
intentionally followed NeMo 2.5: it changed reflected STFT padding to constant
padding, removed the extra valid frame, and added waveform-length masking.
NVIDIA's [NeMo 2.4 source](https://github.com/NVIDIA/NeMo/blob/v2.4.0/nemo/collections/asr/parts/preprocessing/features.py)
and [NeMo 2.5 source](https://github.com/NVIDIA/NeMo/blob/v2.5.0/nemo/collections/asr/parts/preprocessing/features.py)
confirm the valid-length change. Neither compared frontend adds dither; the
fixed seed therefore does not resolve their deterministic version difference.

The conversion card does not pin the exact NeMo/PyTorch versions used for this
model's export. A controlled diagnostic using the same int8 weights and the
model-supplied legacy frontend has been separately authorized and frozen in
[legacy-frontend-ablation](../legacy-frontend-ablation/plan.json). This comparison
does not silently select that frontend or revise any existing recognition output.
