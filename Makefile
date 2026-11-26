PY ?= python3
# one RUN_ID per `make` invocation groups all its lines in runs.jsonl
export RUN_ID := $(shell date -u +%Y%m%dT%H%M%SZ)

.PHONY: film radio setup smoke validate draft translate narration keyframes refs shots music assemble gpu-jobs costs clean-final

## Whole pipeline from storyboard.json. Cached: only changed shots regenerate.
film: validate narration keyframes shots music assemble

## Radio cut: narration + temp music on black (needs only the Gemini key)
radio: validate narration
	$(PY) -m pipeline.assemble --radio

setup:
	$(PY) -m pip install -r requirements.txt
	@test -f .env || (cp .env.example .env && echo "created .env - fill in your keys")

smoke:
	$(PY) -m pipeline.smoke_test

validate:
	$(PY) -m pipeline.validate

draft:
	$(PY) -m pipeline.script draft --notes story/notes.md

translate:
	$(PY) -m pipeline.script translate

narration:
	$(PY) -m pipeline.narration

refs:
	$(PY) -m pipeline.keyframes --refs-only

keyframes:
	$(PY) -m pipeline.keyframes

shots:
	$(PY) -m pipeline.shots

music:
	$(PY) -m pipeline.music

assemble:
	$(PY) -m pipeline.assemble

gpu-jobs:
	$(PY) -m pipeline.export_gpu_jobs

costs:
	$(PY) -m pipeline.costs

clean-final:
	rm -rf outputs/final outputs/tmp
