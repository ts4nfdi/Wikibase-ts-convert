# Pipeline for the Climate Policy Radar vocabulary

## Overview

This script queries data from the [Climate Policy Radar](https://climatepolicyradar.wikibase.cloud/wiki/Main_Page) by only including subconcepts of [Target](https://climatepolicyradar.wikibase.cloud/wiki/Item:Q1651) and [Policy Instrument](https://climatepolicyradar.wikibase.cloud/wiki/Item:Q1171).

### Input

- Source: https://climatepolicyradar.wikibase.cloud/query/

### Output

The output of this pipeline will be generated in the `out` directory within this pipeline's directory.

- Filename: `ClimatePolicyRadar.owl`

## Setup

This pipeline should be executed from `main.py` in the `Wikibase-ts-convert` directory.

To execute only this pipeline:

```
# this command has to be executed from the Wikibase-ts-convert folder
python main.py cpr
```