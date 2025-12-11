# OLS4 JSON config generator

## About
This script queries data for the [OhdAB](https://database.factgrid.de/wiki/FactGrid:OhdAB-Datenbank) from FactGrid and 
saves it in a turtle file.


# Built With
* python3.9
* SPARQLWrapper
* rdflib

### Setup

To start the application do the following steps:

```
# If not created, create virtualenv
python3 -m venv venv 
# Activate virtualenv
source ./venv/bin/activate
# Update pip
pip install --upgrade pip
# Install dependencies
pip install -r ./requirements.txt 
# run code
python main.py 
```
