# Pipeline for the OhdAB ontology

## Overview

This script queries data for the [OhdAB](https://database.factgrid.de/wiki/FactGrid:OhdAB-Datenbank) from FactGrid and
saves it in a turtle file.

### Input

- Source: https://database.factgrid.de/sparql

### Output

The output of this pipeline will be generated in the `out` directory within this pipeline's directory.

- Filename: `OhdAB.ttl`

### Cache files

The pipeline creates cache files, which can be enabled for use in the script if desired. The cache files are generated
in the `resources` directory within this pipeline folder.

## Setup

This pipeline should be executed from `main.py` in the `Wikibase-ts-convert` directory.

To execute only this pipeline:

```
# this command has to be executed from the ontology-pipelines folder
python main.py ohdab
```