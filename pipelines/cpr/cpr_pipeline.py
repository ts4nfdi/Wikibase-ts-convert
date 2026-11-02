import requests
from pathlib import Path
from rdflib import Graph, URIRef, Literal, Namespace
import subprocess
from rdflib.namespace import OWL, RDF, RDFS, DCTERMS, SDO, SKOS, FOAF

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "out"


# sparql endpoint
ENDPOINT = "https://climatepolicyradar.wikibase.cloud/query/sparql"

# root classes
ROOT_CLASSES = [
    "Q32", "Q47", "Q218", "Q557", "Q567", "Q638", "Q672",
    "Q709", "Q975", "Q1171", "Q1343", "Q1367", "Q1651", "Q1829"
]

ROOT_VALUES = " ".join(f"wd:{root}" for root in ROOT_CLASSES)

# prefixes for queries
PREFIXES = """
PREFIX wd: <https://climatepolicyradar.wikibase.cloud/entity/>
PREFIX wdt: <https://climatepolicyradar.wikibase.cloud/prop/direct/>
"""

# namespaces
CPR = Namespace("https://climatepolicyradar.wikibase.cloud/entity/")
ONTOLOGY_URI = URIRef("https://climatepolicyradar.wikibase.cloud/wiki/")

# queries
# all queries are restricted to entities that are descendants of root classes, regardless of hierarchy depth.

# labels, descriptions and altLabels get returned in one string each where multiple values are separated through |SEP|.
# If no value exists it still returns an empty string.
CLASSES_QUERY = f"""
{PREFIXES}
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?entity
       (GROUP_CONCAT(DISTINCT ?label; separator="|SEP|") AS ?entityLabel)
       (GROUP_CONCAT(DISTINCT ?description; separator="|SEP|") AS ?entityDescription)
       (GROUP_CONCAT(DISTINCT ?altLabel; separator="|SEP|") AS ?entityAltLabel)
WHERE {{
  {{
    SELECT DISTINCT ?entity
    WHERE {{
      VALUES ?root {{ {ROOT_VALUES} }}
      ?entity wdt:P2* ?root .
    }}
  }}

  OPTIONAL {{
    ?entity rdfs:label ?label .
    FILTER(LANG(?label) = "en")
  }}

  OPTIONAL {{
    ?entity schema:description ?description .
    FILTER(LANG(?description) = "en")
  }}

  OPTIONAL {{
    ?entity skos:altLabel ?altLabel .
    FILTER(LANG(?altLabel) = "en")
  }}
}}
GROUP BY ?entity
"""

PROPERTIES_QUERY = f"""
{PREFIXES}
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

SELECT ?property
       (GROUP_CONCAT(DISTINCT ?label; separator="|SEP|") AS ?propertyLabel)
       (GROUP_CONCAT(DISTINCT ?description; separator="|SEP|") AS ?propertyDescription)
       (GROUP_CONCAT(DISTINCT ?altLabel; separator="|SEP|") AS ?propertyAltLabel)
WHERE {{
  {{
    SELECT DISTINCT ?property
    WHERE {{
      VALUES ?root {{ {ROOT_VALUES} }}
      ?entity wdt:P2* ?root .
      ?entity ?directProperty ?value .
      ?property wikibase:directClaim ?directProperty .
    }}
  }}

  OPTIONAL {{
    ?property rdfs:label ?label .
    FILTER(LANG(?label) = "en")
  }}

  OPTIONAL {{
    ?property schema:description ?description .
    FILTER(LANG(?description) = "en")
  }}

  OPTIONAL {{
    ?property skos:altLabel ?altLabel .
    FILTER(LANG(?altLabel) = "en")
  }}
}}
GROUP BY ?property
"""

TRIPLES_QUERY = f"""
{PREFIXES}
SELECT DISTINCT ?entity ?property ?value
WHERE {{
  VALUES ?root {{ {ROOT_VALUES} }}

  ?entity wdt:P2* ?root .

  ?entity ?directProperty ?value .

  ?property wikibase:directClaim ?directProperty .

  FILTER(
    ?property != wd:P2 ||
    EXISTS {{
      ?value wdt:P2* ?root .
    }}
  )
}}
"""

SAME_AS_QUERY = f"""
{PREFIXES}
SELECT ?entity ?replacement
WHERE {{
  VALUES ?root {{ {ROOT_VALUES} }}
  
  ?entity owl:sameAs ?replacement .
  
  ?replacement wdt:P2* ?root
}}
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


def add_classes_to_graph(classes, graph):
    for entry in classes:
        entity_uri = URIRef(entry["entity"]["value"])

        graph.add((entity_uri, RDF.type, OWL.Class))

        if entry["entityLabel"]["value"] != "":
            for label in entry["entityLabel"]["value"].split("|SEP|"):
                graph.add((entity_uri, RDFS.label, Literal(label, lang="en")))
        if entry["entityDescription"]["value"] != "":
            for description in entry["entityDescription"]["value"].split("|SEP|"):
                graph.add((entity_uri, SDO.description, Literal(description, lang="en")))
        if entry["entityAltLabel"]["value"] != "":
            for alt_label in entry["entityAltLabel"]["value"].split("|SEP|"):
                graph.add((entity_uri, SKOS.altLabel, Literal(alt_label, lang="en")))
    print(f"added {len(classes)} classes to graph")


def add_properties_to_graph(properties, graph):
    for entry in properties:

        if entry["property"]["value"] == str(CPR.P1) or entry["property"]["value"] == str(CPR.P2):
            continue

        property_uri = URIRef(entry["property"]["value"])

        graph.add((property_uri, RDF.type, OWL.AnnotationProperty))

        if entry["propertyLabel"]["value"] != "":
            for label in entry["propertyLabel"]["value"].split("|SEP|"):
                graph.add((property_uri, RDFS.label, Literal(label, lang="en")))
        if entry["propertyDescription"]["value"] != "":
            for description in entry["propertyDescription"]["value"].split("|SEP|"):
                graph.add((property_uri, SDO.description, Literal(description, lang="en")))
        if entry["propertyAltLabel"]["value"] != "":
            for alt_label in entry["propertyAltLabel"]["value"].split("|SEP|"):
                graph.add((property_uri, SKOS.altLabel, Literal(alt_label, lang="en")))
    print(f"added {len(properties) -2} properties to graph")


def create_same_as_map(same_as_classes):
    same_as_map = {}
    for entry in same_as_classes:
        entity_uri = URIRef(entry["entity"]["value"])
        replacement_uri = URIRef(entry["replacement"]["value"])
        same_as_map[entity_uri] = replacement_uri
    return same_as_map


def add_triples_to_graph(triples, graph, same_as_map):
    for entry in triples:
        subject = URIRef(entry["entity"]["value"])

        predicate = URIRef(entry["property"]["value"])

        if entry["value"]["type"] == "uri":
            obj = URIRef(entry["value"]["value"])
            if obj in same_as_map:
                obj = same_as_map[obj]
        else:
            obj = Literal(entry["value"]["value"], lang="en")

        # P1 is hasSubclass -> for subClassOf subject and object need to be switched
        if predicate == CPR.P1:
            graph.add((obj, RDFS.subClassOf, subject))
        # P2 is subClassOf -> only add if subject is no root class
        elif predicate == CPR.P2:
            if subject not in {CPR[root] for root in ROOT_CLASSES}:
                graph.add((subject, RDFS.subClassOf, obj))
        else:
            graph.add((subject, predicate, obj))

    print(f"added {len(triples)} triples to graph")


def add_ontology_metadata(graph):
    graph.add((ONTOLOGY_URI, RDF.type, OWL.Ontology))

    # title
    graph.add((ONTOLOGY_URI, DCTERMS.title, Literal("Climate Policy Radar - concept store", lang="en")))

    # label
    graph.add((ONTOLOGY_URI, RDFS.label, Literal("Climate Policy Radar - concept store", lang="en")))

    # description
    graph.add((ONTOLOGY_URI, DCTERMS.description, Literal("The concept store is an internal tool used to "
                                                          "structure and manage key concepts in climate policy. It "
                                                          "helps power automated concept detection in our datasets. ",
                                                          lang="en")))

    # homepage
    graph.add((ONTOLOGY_URI, FOAF.homepage, Literal("https://www.climatepolicyradar.org/",
                                                    lang="en")))

    # license
    graph.add((ONTOLOGY_URI, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))

    print("added ontology metadata to graph")


def serialize_graph(graph):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    output_file = "cpr.owl"

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
            str(OUT_DIR / "cpr.owl"),
            str(OUT_DIR / "cpr.owl")
        ],
        check=True
    )


def main():
    graph = Graph()

    graph.bind("cpr", CPR)

    add_ontology_metadata(graph)

    classes = get_answer_from_endpoint(CLASSES_QUERY)
    add_classes_to_graph(classes, graph)

    properties = get_answer_from_endpoint(PROPERTIES_QUERY)
    add_properties_to_graph(properties, graph)

    same_as_classes = get_answer_from_endpoint(SAME_AS_QUERY)
    same_as_map = create_same_as_map(same_as_classes)

    triples = get_answer_from_endpoint(TRIPLES_QUERY)
    add_triples_to_graph(triples, graph, same_as_map)

    serialize_graph(graph)

    apply_formatter()


if __name__ == "__main__":
    main()
