# Development
## Linter

This repository uses [flake8](https://flake8.pycqa.org/en/latest/index.html) as its linter, consistent with the upstream Traceloop repository.

To run Flake8 locally, activate your virtual environment and execute:
```
flake8
```

Flake8 is automatically run on every pull request as part of the `code-unit-tests` step in the PR-pipeline. To view the linter report, search for `==== flake8 linter output` in the `run-stage` output.