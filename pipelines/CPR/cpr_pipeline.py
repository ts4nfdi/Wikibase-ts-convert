import requests
from pathlib import Path
from rdflib import Graph, URIRef, Literal, Namespace
import subprocess
from rdflib.namespace import OWL, RDF, RDFS, DCTERMS, SDO, SKOS

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "out"


# sparql endpoint
ENDPOINT = "https://climatepolicyradar.wikibase.cloud/query/sparql"

# namespaces
OMW = Namespace("https://climatepolicyradar.wikibase.cloud/entity/")
ONTOLOGY_URI = URIRef("https://climatepolicyradar.wikibase.cloud/wiki/")

# queries
# all queries are restricted to individuals that are descendants of Q1171 or Q1651, regardless of hierarchy depth.
INDIVIDUALS_QUERY = """
PREFIX wd: <https://climatepolicyradar.wikibase.cloud/entity/>
PREFIX wdt: <https://climatepolicyradar.wikibase.cloud/prop/direct/>

SELECT DISTINCT ?entity ?entityLabel ?entityDescription ?entityAltLabel
WHERE {
  VALUES ?root {
    wd:Q1171
    wd:Q1651
  }

  ?entity wdt:P2+ ?root .

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
"""

PROPERTIES_QUERY = """
PREFIX wd: <https://climatepolicyradar.wikibase.cloud/entity/>
PREFIX wdt: <https://climatepolicyradar.wikibase.cloud/prop/direct/>

SELECT DISTINCT
  ?property
  ?propertyLabel
  ?propertyDescription
  ?propertyAltLabel
WHERE {
    VALUES ?root {
    wd:Q1171
    wd:Q1651
  }

  ?entity wdt:P2+ ?root .
  
  ?entity ?directProperty ?value .

  ?property wikibase:directClaim ?directProperty .

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
"""


TRIPLES_QUERY = """
PREFIX wd: <https://climatepolicyradar.wikibase.cloud/entity/>
PREFIX wdt: <https://climatepolicyradar.wikibase.cloud/prop/direct/>

SELECT DISTINCT ?entity ?property ?value
WHERE {
  VALUES ?root {
    wd:Q1171
    wd:Q1651
  }

  ?entity wdt:P2+ ?root .

  ?entity ?directProperty ?value .

  ?property wikibase:directClaim ?directProperty .
}
"""

def get_answer_from_endpoint(query):
    response = requests.get(
        ENDPOINT,
        params={"query": query},
        headers={
            "Accept": "application/sparql-results+json"
        }
    )

    response.raise_for_status()

    return response.json()["results"]["bindings"]

def add_individuals_to_graph(individuals, graph):
    for entry in individuals:
        entity_uri = URIRef(entry["entity"]["value"])

        graph.add((entity_uri, RDF.type, OWL.NamedIndividual))

        if "entityLabel" in entry:
            graph.add((entity_uri, RDFS.label, Literal(entry["entityLabel"]["value"], lang="en")))
        if "entityDescription" in entry:
            graph.add((entity_uri, SDO.description, Literal(entry["entityDescription"]["value"], lang="en")))
        if "entityAltLabel" in entry:
            graph.add((entity_uri, SKOS.altLabel, Literal(entry["entityAltLabel"]["value"], lang="en")))

    print(f"added {len(individuals)} individuals to graph")

def add_properties_to_graph(properties, graph):
    for entry in properties:
        property_uri = URIRef(entry["property"]["value"])

        graph.add((property_uri, RDF.type, OWL.AnnotationProperty))

        if "propertyLabel" in entry:
            graph.add((property_uri, RDFS.label, Literal(entry["propertyLabel"]["value"], lang="en")))
        if "propertyDescription" in entry:
            graph.add((property_uri, SDO.description, Literal(entry["propertyDescription"]["value"], lang="en")))
        if "propertyAltLabel" in entry:
            graph.add((property_uri, SKOS.altLabel, Literal(entry["propertyAltLabel"]["value"], lang="en")))

    print(f"added {len(properties)} properties to graph")


def add_triples_to_graph(triples, graph):
    for entry in triples:
        individual = URIRef(entry["entity"]["value"])
        predicate = URIRef(entry["property"]["value"])

        if entry["value"]["type"] == "uri":
            graph.add((individual, predicate, URIRef(entry["value"]["value"])))
        else:
            graph.add((individual, predicate, Literal(entry["value"]["value"], lang="en")))

    print(f"added {len(triples)} triples to graph")


def add_ontology_metadata(graph):
    graph.add((ONTOLOGY_URI, RDF.type, OWL.Ontology))

    # title
    graph.add((ONTOLOGY_URI, DCTERMS.title, Literal("Climate Policy Radar", lang="en")))

    # label
    graph.add((ONTOLOGY_URI, RDFS.label, Literal("Climate Policy Radar", lang="en")))

    # description
    # graph.add((ONTOLOGY_URI, DCTERMS.description, Literal("To be added", lang="en")))

    # license
    graph.add((ONTOLOGY_URI, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))

    print("added ontology metadata to graph")


def serialize_graph(graph):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = "ClimatePolicyRadar.owl"

    graph.serialize(
        destination=OUT_DIR / output_file,
        format="pretty-xml"
    )

    print(f"serialized graph to {output_file}")


def apply_formatter():
    subprocess.run(
        [
            "java",
            "-jar",
            str(BASE_DIR.parent / "resources" / "ontology-formatter.jar"),
            str(OUT_DIR / "ClimatePolicyRadar.owl"),
            str(OUT_DIR / "ClimatePolicyRadar.owl")
        ],
        check=True
    )


def main():
    graph = Graph()

    graph.bind("cpr", OMW)

    add_ontology_metadata(graph)

    individuals = get_answer_from_endpoint(INDIVIDUALS_QUERY)
    add_individuals_to_graph(individuals, graph)

    properties = get_answer_from_endpoint(PROPERTIES_QUERY)
    add_properties_to_graph(properties, graph)

    triples = get_answer_from_endpoint(TRIPLES_QUERY)
    add_triples_to_graph(triples, graph)

    serialize_graph(graph)

    apply_formatter()


if __name__ == "__main__":
    main()
