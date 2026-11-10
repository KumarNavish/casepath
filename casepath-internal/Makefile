# make           list what you can do
# Uses .venv/bin/python when `make setup` made it, else python3.
PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

help:  ## this list
	@grep -E "^[a-z-]+:.*## " $(MAKEFILE_LIST) | sed -E "s/:.*## /\t/" | expand -t 10

setup:  ## .venv with everything CasePath needs
	python3 -m venv .venv && .venv/bin/pip install -q -e ".[azure]"

test:  ## every test; no network, no model
	$(PY) -m unittest discover -s tests -t .

preview:  ## the workspace on synthetic cases, scripted model: http://127.0.0.1:8790
	$(PY) deploy/preview/preview.py 8790 1.5

serve:  ## the real workspace, configured from the environment (deploy/workspace/env.example)
	$(PY) -m casepath serve

package:  ## build/casepath-app: the folder the Databricks App runs from
	PYTHON=$(PY) deploy/databricks/package.sh build/casepath-app

contract:  ## after an API change: rewrite docs/contracts/case-api.openapi.json
	$(PY) -m casepath contract --write

.PHONY: help setup test preview serve package contract
