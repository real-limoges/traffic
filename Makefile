.PHONY: all data artifacts paper clean

all: artifacts paper

# Phase 1 (Fable) territory — fetch raw data and produce cleaned intermediate
# data. Should be idempotent: safe to re-run without re-fetching what's
# already in data/raw/ unless explicitly forced.
data:
	@echo "define data acquisition + cleaning steps here -> data/processed/"

# Phase 1 (Fable) territory — transform data/processed/ into the stable
# artifacts/ contract, per SCHEMA.md. This is the line Fable's scope stops
# at; nothing past this target is Fable's job.
artifacts: data
	@echo "define artifact-generation steps here -> artifacts/"

# Phase 2 (Opus) territory, plus paper rendering — reads only from
# artifacts/, never from data/ directly.
paper: artifacts
	quarto render paper/paper.qmd

clean:
	rm -rf data/processed artifacts/*.parquet artifacts/*.json paper/*.pdf
