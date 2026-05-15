# Wikibase ts convert

## About

This repository contains the multiple ontology pipelines to convert external terminologies to RDF files. These files
could be than indexed to OLS based systems such as SemLookP.

## Requirements

* python3.9
* SPARQLWrapper
* rdflib

## Setup

To execute the pipelines run the following commands:

### create or start virtual environment

```
# If not created, create virtualenv
python3 -m venv venv 
# Activate virtualenv
source ./venv/bin/activate
# Update pip
pip install --upgrade pip
# Install dependencies
pip install -r ./requirements.txt 
```

### Run script

There are multiple options how to run the pipelines:

**Run all pipelines:**

```
python main.py
# or
python main.py all
```

**Run only selected pipelines:**
Pass one or more pipeline names as arguments, separated by spaces:

```
python main.py <pipeline1> <pipeline2> <pipeline3> ...
```

Available pipelines:

- ohdab
- mathmod

Examples:

```
# Run a single pipeline
python main.py ohdab

# Run multiple pipelines
python main.py ohdab mathmod
```

**Remove all output and cache data:**

```
python main.py remove
```

## Output

The output of each pipeline is generated in the `out` directory of the respective pipeline folder. Cache files get
stored in the respective `resource` directory.