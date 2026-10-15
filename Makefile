SCOPE ?= patch
VERSION ?=
DRY_RUN ?= true

.PHONY: bump version
version:
	@cat VERSION

bump:
	python3 scripts/bump.py $(if $(VERSION),$(VERSION),$(SCOPE)) $(if $(filter false,$(DRY_RUN)),--apply,)
