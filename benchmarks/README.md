# Local image model benchmarks

Compare local image quality and runtime before changing the live grid. These commands never register a worker, spend credits, contact a coordinator, or call a cloud image-generation API. A first run downloads model weights from Hugging Face; later runs can use --local-only.

## Run

Use the Python worker environment from workers/python/README.md. Run each model in a separate process so model memory is released between comparisons. Use the same resolution, prompts, seeds and thread limit; use each model's appropriate inference settings.

```sh
workers/python/.venv/bin/python benchmarks/run.py --model tiny-sd --backend cpu --size 512 --output .cache/benchmarks/tiny-sd-512
workers/python/.venv/bin/python benchmarks/run.py --model sd-turbo --backend cpu --size 512 --output .cache/benchmarks/sd-turbo-512
```

Each output directory must be new. Open its index.html to compare images, and inspect results.json for timings and environment metadata. Outputs stay in the ignored .cache directory. Default runs cover five prompts with two seeds each; --limit 3 --repeats 2 gives a smaller first comparison. This sample is exploratory, not enough to claim production p95 or universal quality superiority.

Use --backend mps from a Mac process with Apple GPU access, or --backend cuda on a configured NVIDIA machine. Explicit unavailable backends fail rather than silently changing the comparison. CPU threads are not a GPU utilization or memory cap. Do not run concurrent generation benchmarks if comparing latency.

SDXL-Turbo is available with --model sdxl-turbo, but is not automatically downloaded or selected. Measure its extra memory and latency before using it in a demo.

## Model profiles

| Profile | Default smoke size | Default steps | Guidance | Status |
| --- | --- | --- | --- | --- |
| tiny-sd | 256 | 12 | 7.5 | Existing grid default |
| sd-turbo | 512 | 4 | 0 | Benchmark only |
| sdxl-turbo | 512 | 4 | 0 | Benchmark only |

Revisions are pinned in workers/python/worker.py. Turbo weights load from the fp16 variant, converted to FP32 for CPU execution. Turbo profiles accept one to four benchmark steps. The existing coordinator accepts four to thirty steps and has no model-selection field; experimental profiles are therefore blocked in worker run mode until a reviewed routing contract exists. A failed experimental load never falls back to cloud or substitutes a different model.

The Turbo model cards specify guidance_scale=0 and recommend 512px. SD-Turbo's published pipeline does not include a safety checker; the benchmark records whether one is present. This is another reason to keep the experimental path separate from deployment. Preserve the existing Tiny-SD checker. Follow the model publisher's license when deciding how to deploy.

Sources: https://huggingface.co/segmind/tiny-sd, https://huggingface.co/stabilityai/sd-turbo, https://huggingface.co/stabilityai/sdxl-turbo.

## Interpret results

Load time includes downloads if not cached; do not label it pure cold-start latency. First inference is recorded separately. Warm inference includes image encoding but excludes planning, queue time, transfers and phone finalization. Process RSS is sampled every 50ms and is not total GPU memory. Apple shared GPU memory and CUDA allocator usage need separate measurements before setting memory-based routing thresholds.

Review the gallery for recognizable subjects, unwanted artifacts, correct spatial relations and prompt fidelity. Same seeds aid repeatability within a model but do not make different architectures generate the same composition. Record human judgments separately from measured timings. Check several prompts before preferring a model.

Next integration requires an agreed model ID/revision field, device model capability reporting, compatible retry behavior, explicit cloud permission and per-model estimates. Keep that coordinator work on the teammate's side of the ownership split.
