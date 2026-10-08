.PHONY: test up down smoke load kind drill monitoring clean-lab

test:
	python -m pytest -q
	ruff check app tests scripts
	helm lint deploy/chart
up:
	./scripts/init-env.sh
	docker compose up --build -d
smoke:
	@set -a; . ./.env; set +a; python3 scripts/smoke.py
load:
	@set -a; . ./.env; set +a; python3 scripts/load.py
kind:
	./scripts/kind-up.sh
drill:
	./scripts/drill.sh
monitoring:
	helm upgrade modelops deploy/chart --kube-context kind-modelops-lab -n modelops --reuse-values --set monitoring.enabled=true --wait --timeout 5m
down:
	docker compose down
clean-lab:
	kind delete cluster --name modelops-lab
