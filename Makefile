.PHONY: all data artifacts paper test pin-raw clean

all: artifacts paper

# Phase 1 (Fable) territory — parse raw PeMS pulls into cleaned intermediate
# data. Idempotent over data/raw/: never fetches (the PeMS pull is a manual,
# registered-account step — see data/raw/README.md), never edits raw files.
data:
	python3 -m pipeline.run data

# Phase 1 (Fable) territory — transform data/processed/ into the stable
# artifacts/ contract, per artifacts/SCHEMA.md. This is the line Fable's
# scope stops at; nothing past this target is Fable's job.
artifacts: data
	python3 -m pipeline.run graph

# Phase 2 (Opus) territory, plus paper rendering — reads only from
# artifacts/, never from data/ directly.
paper: artifacts
	quarto render paper/paper.qmd

# Pipeline mechanics verified against a synthetic PeMS-format fixture with
# planted ground truth (tests/). No real data required.
test:
	python3 -m pytest tests/ -q

# Record checksums of the raw pull for PROVENANCE.md.
pin-raw:
	cd data/raw && find . -type f ! -name SHA256SUMS -print0 | sort -z | \
	  xargs -0 sha256sum > SHA256SUMS && cat SHA256SUMS

clean:
	rm -rf data/processed artifacts/network_graph.json paper/*.pdf
