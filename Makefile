VERSION ?=
DRY_RUN ?= true
NEXT_DEV ?=

.PHONY: release version
version:
	@cat VERSION

# A human selects VERSION; preview is the default, following makefile-go.
release:
	@test -n "$(VERSION)" || (echo 'Usage: make release VERSION=0.4.0 [DRY_RUN=false] [NEXT_DEV=0.4.1]'; exit 1)
	python3 scripts/release.py $(VERSION) $(if $(filter false,$(DRY_RUN)),--apply,) $(if $(NEXT_DEV),--next-dev $(NEXT_DEV),)
