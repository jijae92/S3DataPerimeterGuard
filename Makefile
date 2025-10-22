.PHONY: up test simulate deploy clean

VENV=.venv
PYTHON=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

up:
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	npm ci --prefix dashboard

simulate:
	$(PYTHON) tools/simulator.py run \
		--bucket $$TARGET_BUCKET \
		--policy-file policies/bucket-policy.base.json \
		--scps policies/scp-set.json \
		--iam-roles data/iam-roles.json \
		--output artifacts/findings.json

test:
	$(PYTHON) -m pytest --cov=tools --cov=simulator tests

deploy:
	sam build
	sam deploy --guided

clean:
	rm -rf $(VENV) .pytest_cache artifacts/findings.json
	npm --prefix dashboard run clean || true
