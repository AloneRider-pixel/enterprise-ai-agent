# Evidence and reproducibility policy

This repository distinguishes implementation capability from measured results.

## What counts as evidence

A quantitative engineering claim should be reproducible from repository-controlled inputs. A published result should identify:

- the dataset or workload and its version;
- the exact command or workflow used;
- relevant dependency/tool versions;
- the runtime environment;
- sample count, workload size, or denominator;
- the commit SHA that produced the result;
- the generated artifact when practical.

## Claim categories

**Capability** describes what the code implements.

**Design target** describes an intended threshold or SLO and is not a measured result.

**Measured result** is produced by a repeatable benchmark or evaluation and should be accompanied by its methodology and artifact.

**Synthetic/demo data** is for UI or workflow validation and must not be presented as production performance or model-quality evidence.

## Review rule

Do not add a performance, accuracy, reliability, scale, or cost number to the README unless a reviewer can follow the linked implementation and reproduce the measurement.

The CI workflow is a build-and-test signal. A green workflow proves that the configured verification steps passed; it does not by itself prove production performance.

## Local verification

Use the commands in the README and CI workflow. When a claim is measured, preserve the resulting artifact and document the exact experiment conditions.
