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

# namespaces
CPR = Namespace("https://climatepolicyradar.wikibase.cloud/entity/")
ONTOLOGY_URI = URIRef("https://climatepolicyradar.wikibase.cloud/wiki/")

# queries
# all queries are restricted to entities that are descendants of Q1171 or Q1651, regardless of hierarchy depth.
CLASSES_QUERY = f"""
PREFIX wd: <https://climatepolicyradar.wikibase.cloud/entity/>
PREFIX wdt: <https://climatepolicyradar.wikibase.cloud/prop/direct/>

SELECT DISTINCT ?entity ?entityLabel ?entityDescription ?entityAltLabel
WHERE {{
  VALUES ?root {{ {ROOT_VALUES} }}

  ?entity wdt:P2* ?root .

  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
  }}
}}
"""

PROPERTIES_QUERY = f"""
PREFIX wd: <https://climatepolicyradar.wikibase.cloud/entity/>
PREFIX wdt: <https://climatepolicyradar.wikibase.cloud/prop/direct/>

SELECT DISTINCT
  ?property
  ?propertyLabel
  ?propertyDescription
  ?propertyAltLabel
WHERE {{
    VALUES ?root {{ {ROOT_VALUES} }}

  ?entity wdt:P2* ?root .
  
  ?entity ?directProperty ?value .

  ?property wikibase:directClaim ?directProperty .

  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
  }}
}}
"""

TRIPLES_QUERY = f"""
PREFIX wd: <https://climatepolicyradar.wikibase.cloud/entity/>
PREFIX wdt: <https://climatepolicyradar.wikibase.cloud/prop/direct/>

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
PREFIX wd: <https://climatepolicyradar.wikibase.cloud/entity/>
PREFIX wdt: <https://climatepolicyradar.wikibase.cloud/prop/direct/>
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

        if "entityLabel" in entry:
            graph.add((entity_uri, RDFS.label, Literal(entry["entityLabel"]["value"], lang="en")))
        if "entityDescription" in entry:
            graph.add((entity_uri, SDO.description, Literal(entry["entityDescription"]["value"], lang="en")))
        if "entityAltLabel" in entry:
            graph.add((entity_uri, SKOS.altLabel, Literal(entry["entityAltLabel"]["value"], lang="en")))

    print(f"added {len(classes)} classes to graph")

def add_properties_to_graph(properties, graph):
    for entry in properties:

        if entry["property"]["value"] == str(CPR.P1) or entry["property"]["value"] == str(CPR.P2):
            continue

        property_uri = URIRef(entry["property"]["value"])

        graph.add((property_uri, RDF.type, OWL.AnnotationProperty))

        if "propertyLabel" in entry:
            graph.add((property_uri, RDFS.label, Literal(entry["propertyLabel"]["value"], lang="en")))
        if "propertyDescription" in entry:
            graph.add((property_uri, SDO.description, Literal(entry["propertyDescription"]["value"], lang="en")))
        if "propertyAltLabel" in entry:
            graph.add((property_uri, SKOS.altLabel, Literal(entry["propertyAltLabel"]["value"], lang="en")))

    print(f"added {len(properties)} properties to graph")


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
    print(same_as_map)

    triples = get_answer_from_endpoint(TRIPLES_QUERY)
    add_triples_to_graph(triples, graph, same_as_map)

    serialize_graph(graph)

    apply_formatter()


if __name__ == "__main__":
    main()
