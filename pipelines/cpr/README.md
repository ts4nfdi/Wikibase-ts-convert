# Pipeline for the Climate Policy Radar vocabulary

## Overview

This script queries data from the [Climate Policy Radar](https://climatepolicyradar.wikibase.cloud/wiki/Main_Page) by only including subconcepts of 
Q32, Q47, Q218, Q557, Q567, Q638, Q672, Q709, Q975, Q1171, Q1343, Q1367, Q1651 and Q1829.

### Input

- Source: https://climatepolicyradar.wikibase.cloud/query/

### Output

The output of this pipeline will be generated in the `out` directory within this pipeline's directory.

- Filename: `cpr.owl`

## Setup

This pipeline should be executed from `main.py` in the `Wikibase-ts-convert` directory.

To execute only this pipeline:

```
# this command has to be executed from the Wikibase-ts-convert folder
python main.py cpr
```