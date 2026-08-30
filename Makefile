.PHONY: dev-up dev-down lint test demo-data terraform-validate k8s-render

dev-up:
	docker compose up -d --build

dev-down:
	docker compose down

lint:
	cd backend && ruff check app tests
	cd frontend && npm run lint

test:
	cd backend && pytest -q
	cd frontend && npm test

demo-data:
	python scripts/generate_demo_images.py

terraform-validate:
	cd infra/terraform && terraform fmt -check -recursive && terraform init -backend=false && terraform validate

k8s-render:
	kubectl kustomize infra/kubernetes
