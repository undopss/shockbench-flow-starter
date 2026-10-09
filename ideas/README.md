# Agent ideas archive

This folder is the durable inbox and index for agent optimization ideas. Add new ideas here before implementation so
that hypotheses, evidence, rejected approaches, and follow-up experiments stay together.

- [`AGENT_OPTIMIZATION_IDEAS.md`](AGENT_OPTIMIZATION_IDEAS.md) contains the Pulse v2 eleven, mentor notes, measured
  findings, current implementation problems, and ranked next experiments.
- [`PULSE_V2_DETAILED_AUDIT.md`](PULSE_V2_DETAILED_AUDIT.md) is the source-level audit of the newest experimental
  agent, with concrete model defects, confidence levels, and an implementation order.
- [`../CLOUD_TASKS.md`](../CLOUD_TASKS.md) contains runnable task specifications. Keep task instructions linked to
  this archive rather than duplicating long analysis in several places.

For every new idea, record: the failure it targets, the mechanism that could fix it, confidence/evidence, an experiment
that can falsify it, the evaluation set, and the result/status. Do not label an idea “best” based on one episode or on
cost savings from runs whose generator/reference hashes do not match.
