.PHONY: test conf nginx-test conf-fixture tf-fmt tf-validate lab-verify lab-verify-longhaul burn-redirector burn-hostname c2-push decoy-up decoy-down

PYTHON ?= python3
TF     := terraform -chdir=terraform
BACKEND_PLACEHOLDER ?= 192.0.2.1
HEADER_PLACEHOLDER  ?= PLACEHOLDERHEADER
# Identity burn: new VM + new EIP. CloudFront origin follows the EIP.
# S3 and the distribution hostname stay. Implant still hits CloudFront, not this IP.
BURN_INSTANCE := aws_instance.redirector
BURN_EIP      := aws_eip.redirector
# Hostname burn: new short-haul dxxxx.cloudfront.net. Long-haul distribution stays.
BURN_HOSTNAME := aws_cloudfront_distribution.edge

test:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m pytest -q

conf:
	$(PYTHON) -m c2_edge_lab.cli policy render-nginx \
		-f policy/redirector.policy.yaml \
		--backend-host $(BACKEND_PLACEHOLDER) \
		--header-value $(HEADER_PLACEHOLDER) \
		-o terraform/templates/redirector.conf.in

nginx-test: conf-fixture
	@if command -v nginx >/dev/null 2>&1; then \
		nginx -t -c "$(CURDIR)/generated/nginx-standalone.conf"; \
	elif command -v docker >/dev/null 2>&1; then \
		docker run --rm --entrypoint nginx \
			-v "$(CURDIR):/work" -w /work \
			nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10 \
			-t -c /work/generated/nginx-standalone.conf; \
	else \
		echo "install nginx or docker to run nginx -t"; exit 1; \
	fi

conf-fixture:
	$(PYTHON) -m c2_edge_lab.cli policy render-nginx \
		-f tests/fixtures/policy.valid.yaml \
		--backend-host 10.42.2.10 \
		--standalone \
		-o generated/nginx-standalone.conf

tf-fmt:
	$(TF) fmt -recursive

tf-validate:
	$(TF) init -backend=false -input=false
	$(TF) validate

lab-verify:
	$(PYTHON) -m c2_edge_lab.cli verify \
		--base-url "$$($(TF) output -raw decoy_url)" \
		--header-name "$$($(TF) output -raw callback_header_name)" \
		--header-value "$$($(TF) output -raw lab_header_value)" \
		--path "$$($(TF) output -raw callback_probe_path)" \
		--user-agent "$$($(TF) output -raw callback_user_agent)" \
		--expect-proxy-body "$$($(TF) output -raw echo_body)"

lab-verify-longhaul:
	$(PYTHON) -m c2_edge_lab.cli verify \
		--base-url "$$($(TF) output -raw longhaul_url)" \
		--header-name "$$($(TF) output -raw callback_header_name)" \
		--header-value "$$($(TF) output -raw lab_header_value)" \
		--path "$$($(TF) output -raw longhaul_probe_path)" \
		--user-agent "$$($(TF) output -raw callback_user_agent)" \
		--expect-proxy-body "$$($(TF) output -raw echo_body)"

burn-redirector:
	@echo "Refusing to apply from make. Redirector identity burn (new VM + new EIP):"
	@echo "  $(TF) apply -replace=$(BURN_INSTANCE) -replace=$(BURN_EIP)"
	@echo "CloudFront origin follows the new EIP. S3 and both CloudFront hostnames stay."
	@echo "If the short-haul CloudFront hostname itself is blocked, that is make burn-hostname."
	@exit 1

burn-hostname:
	@echo "Refusing to apply from make. Short-haul hostname burn (new dxxxx.cloudfront.net):"
	@echo "  $(TF) apply -replace=$(BURN_HOSTNAME)"
	@echo "Long-haul distribution is not replaced. Custom-domain aliases, if any, follow the new edge distribution."
	@exit 1

# Not terraform apply. Operator laptop → S3 stage/ → SSM pull on the private box.
# DEST must be a simple filename so it cannot escape pull_root.
c2-push:
	@test -n "$(FILE)" || { echo "usage: make c2-push FILE=./binary [DEST=name]"; exit 2; }
	@test -f "$(FILE)" || { echo "FILE not found: $(FILE)"; exit 2; }
	@dest="$(or $(DEST),$(notdir $(FILE)))"; \
	echo "$$dest" | grep -Eq '^[A-Za-z0-9._-]+$$' || { echo "DEST must be a simple filename"; exit 2; }; \
	bucket="$$($(TF) output -raw decoy_bucket_name)"; \
	target="$$($(TF) output -raw teamserver_instance_id)"; \
	stage="$$($(TF) output -raw stage_key_prefix)"; \
	root="$$($(TF) output -raw pull_root)"; \
	lib="$$($(TF) output -raw agent_lib_dir)"; \
	aws s3 cp "$(FILE)" "s3://$$bucket/$$stage/$$dest"; \
	cmd_id="$$(aws ssm send-command \
		--instance-ids "$$target" \
		--document-name AWS-RunShellScript \
		--comment "c2-edge-lab stage pull" \
		--parameters "{\"commands\":[\"C2_EDGE_STAGE_PREFIX=$$stage C2_EDGE_PULL_ROOT=$$root python3 $$lib/s3_pull.py s3://$$bucket/$$stage/$$dest $$root/$$dest\"]}" \
		--query Command.CommandId --output text)"; \
	aws ssm wait command-executed --command-id "$$cmd_id" --instance-id "$$target"; \
	echo "pulled $$root/$$dest (command $$cmd_id)"

decoy-up:
	@echo "Refusing to apply from make. Run terraform apply yourself when you are ready."
	@exit 1

decoy-down:
	@echo "Refusing to destroy from make. Run terraform destroy yourself when you are ready."
	@exit 1
