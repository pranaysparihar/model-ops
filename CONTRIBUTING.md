# Contributing

Keep changes tied to an operational problem and include the failure mode they address. Run `make test`; deployment changes also need `make kind && make drill`. Use a small reproducible test before introducing another platform component.

Never commit secrets, kubeconfigs, prompts from real users, or invented benchmark results. Simulator results must be labeled as simulator results. GPU changes need hardware/model/version/workload details. Open an issue before large architectural changes.
