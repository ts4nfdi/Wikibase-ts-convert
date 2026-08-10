from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import OWL, RDF, RDFS, DCTERMS, XSD, SDO
from pathlib import Path
import subprocess

BASE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = BASE_DIR / "resources"

# FactGrid SPARQL endpoint
ENDPOINT = "https://query.portal.mardi4nfdi.de/sparql"

# Namespaces
OMW = Namespace("https://portal.mardi4nfdi.de/entity/")
ONTOLOGY_URI = URIRef("https://portal.mardi4nfdi.de/wiki/")

# helper method for sending a sparql query to the endpoint and cleaning to result
def get_answer_from_endpoint(query):
    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)

    results = sparql.query().convert()
    results = results["results"]["bindings"]

    return results

# =============================================================================
# SPARQL QUERIES
# =============================================================================
# This query pulls all individuals in the mathmoddb scope.
# This query is used to define each individual and add their label and description.
INDIVIDUALS_QUERY = """
SELECT DISTINCT
  ?item
  ?itemId
  ?itemLabel
  ?itemDescription
WHERE {
  ?item wdt:P1495 wd:Q6534265 .

  BIND(
    REPLACE(STR(?item), "^.*/", "")
    AS ?itemId
  )

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
"""

# This query pulls all wikibase properties used by individuals in the mathmoddb scope.
# This query is used to define each property.
PROPERTIES_QUERY = """
SELECT DISTINCT
  ?property
  ?propertyId
  ?propertyLabel
  ?propertyDescription
WHERE {
  ?item wdt:P1495 wd:Q6534265 .
  ?item ?directProperty ?value .

  ?property wikibase:directClaim ?directProperty .

  BIND(
    REPLACE(STR(?property), "^.*/", "")
    AS ?propertyId
  )

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
"""

# This query pulls all classes the mathmoddb scope consists of .
# This query is used to define the classes and their label and description.
CLASSES_QUERY = """
SELECT DISTINCT
  ?class
  ?classLabel
  ?classDescription
WHERE {
  wd:Q6534265 wdt:P265 ?class .

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
"""

# This query pulls one row per property on an individual.
# This query is used to add all properties to the individuals
INDIVIDUAL_PROPERTY_VALUE_QUERY = """
SELECT DISTINCT
  ?item
  ?property
  ?value
WHERE {
  ?item wdt:P1495 wd:Q6534265 .
  ?item ?directProperty ?value .

  ?property wikibase:directClaim ?directProperty .

  FILTER(
    ?property NOT IN (
      wd:P983,
      wd:P984,
      wd:P989
    )
  )
}
"""

# This query pulls one row per annotatedTarget in a formula on an individual.
# This query is used to add the formula as a property and link the linkedTargetItem to the annotatedTarget.
FORMULA_QUERY = """
SELECT DISTINCT
  ?item
  ?formula
  ?annotatedTarget
  ?linkedTargetItem
WHERE {
  ?item wdt:P1495 wd:Q6534265 .

  ?item wdt:P989 ?formula .

  ?item p:P983 ?inDefiningFormStatement .
  ?inDefiningFormStatement ps:P983 ?annotatedTarget .
  ?inDefiningFormStatement pq:P984 ?linkedTargetItem .
}
"""

# =============================================================================
# METHODS FOR ADDING THE DATA OF THE QUERY RESULTS TO THE GRAPH
# =============================================================================
def add_individuals_to_graph(individuals, graph):
    num_individuals = len(individuals)
    for entry in individuals:
        item_uri = URIRef(entry["item"]["value"])

        # some properties are defined as part of the MathMod community and therefore are listed in the query result.
        # Those should not be added as individuals and will later be added as properties with the property query.
        if entry["itemId"]["value"].startswith("P"):
            num_individuals -= 1
            continue

        graph.add((item_uri, RDF.type, OWL.NamedIndividual))

        if "itemLabel" in entry:
            graph.add((item_uri, RDFS.label, Literal(entry["itemLabel"]["value"], lang="en")))

        if "itemDescription" in entry:
            graph.add((item_uri, SDO.description, Literal(entry["itemDescription"]["value"], lang="en")))

    print(f"added {num_individuals} individuals to graph")


def add_classes_to_graph(classes, graph):
    num_classes = len(classes)

    # array that contains the uris of all classes for later use
    classUris = []

    for entry in classes:
        class_uri = URIRef(entry["class"]["value"])

        # class "publication" should not be added
        if class_uri == URIRef("https://portal.mardi4nfdi.de/entity/Q56751"):
            num_classes -= 1
            continue

        classUris.append(class_uri)

        graph.add((class_uri, RDF.type, RDFS.Class))

        if "classLabel" in entry:
            graph.add((class_uri, RDFS.label, Literal(entry["classLabel"]["value"], lang="en")))

        if "classDescription" in entry:
            graph.add(
                (
                    class_uri,
                    SDO.description,
                    Literal(entry["classDescription"]["value"], lang="en"),
                )
            )

    print(f"added {num_classes} classes to graph")
    return classUris


def add_properties_to_graph(properties, graph):
    uris_of_p983_p989 = {}
    for entry in properties:
        property_uri = URIRef(entry["property"]["value"])

        # P983 and P989 should be added as DatatypeProperties and their uris are needed later
        if entry["propertyId"]["value"] in ["P983", "P989"]:
            graph.add((property_uri, RDF.type, OWL.DatatypeProperty))
            if entry["propertyId"]["value"] == "P983":
                uris_of_p983_p989["P983"] = property_uri
            else:
                uris_of_p983_p989["P989"] = property_uri
        else:
            graph.add((property_uri, RDF.type, OWL.AnnotationProperty))

        if "propertyLabel" in entry:
            graph.add((property_uri, RDFS.label, Literal(entry["propertyLabel"]["value"], lang="en")))

        if "propertyDescription" in entry:
            graph.add(
                (
                    property_uri,
                    SDO.description,
                    Literal(entry["propertyDescription"]["value"], lang="en"),
                )
            )

    print(f"added {len(properties)} properties to graph")
    return uris_of_p983_p989


def add_formula_data_to_graph(formula_data, graph, uris_of_p983_p989):

    # This query retrieves the data for P984. It is handled separately because P984
    # is only used as a qualifier on property statements, not as a direct property of individuals.
    p984_query = """
    SELECT
      ?property
      ?propertyLabel
      ?propertyDescription
    WHERE {
      VALUES ?property {
        wd:P984
      }
    
      SERVICE wikibase:label {
        bd:serviceParam wikibase:language "en" .
      }
    }
    """

    p984_data = get_answer_from_endpoint(p984_query)[0]

    # add p984 to graph
    p984 = URIRef(p984_data["property"]["value"])
    graph.add((p984, RDF.type, OWL.AnnotationProperty))
    if "propertyLabel" in p984_data:
        graph.add((p984, RDFS.label, Literal(p984_data["propertyLabel"]["value"], lang="en")))
    if "propertyDescription" in p984_data:
        graph.add((p984, SDO.description, Literal(p984_data["propertyDescription"]["value"], lang="en")))

    # add formulas of individuals
    for entry in formula_data:
        individual_uri = URIRef(entry["item"]["value"])
        formula = Literal(entry["formula"]["value"], lang="en")

        p983 = uris_of_p983_p989["P983"]
        p989 = uris_of_p983_p989["P989"]

        # add defining formula
        graph.add((individual_uri, p989, formula))
        if "annotatedTarget" in entry:
            annotatedTarget = Literal(entry["annotatedTarget"]["value"], lang="en")
            linkedTargetItem = URIRef(entry["linkedTargetItem"]["value"])

            # add in defining formula and symbol represents
            graph.add((individual_uri, p983, annotatedTarget))
            axiom = BNode()
            graph.add((axiom, RDF.type, OWL.Axiom))
            graph.add((axiom, OWL.annotatedSource, individual_uri))
            graph.add((axiom, OWL.annotatedTarget, annotatedTarget))
            graph.add((axiom, OWL.annotatedProperty, p983))
            graph.add((axiom, p984, linkedTargetItem))


def add_individual_property_value_triples_to_graph(ipv, graph, classUris):
    for entry in ipv:
        individual_uri = URIRef(entry["item"]["value"])
        property_uri = URIRef(entry["property"]["value"])
        if entry["value"]["type"] == "uri":
            property_value = URIRef(entry["value"]["value"])
        else:
            property_value = Literal(entry["value"]["value"], lang="en")

        # instance of relations should be added as RDF.type relation
        if property_uri == URIRef("https://portal.mardi4nfdi.de/entity/P31"):
            # only RDF.type relations to classes that mathmoddb consists of should be added
            if property_value in classUris:
                graph.add((individual_uri, RDF.type, property_value))
        else:
            graph.add((individual_uri, property_uri, property_value))

    print(f"added {len(ipv)} triples with individuals as subject and a wikibase property as property to graph")

# =============================================================================
# ADD ONTOLOGY METADATA
# =============================================================================
def add_ontology_metadata(graph):
    graph.add((ONTOLOGY_URI, RDF.type, OWL.Ontology))

    graph.add((ONTOLOGY_URI, OWL.versionIRI, URIRef(f"{ONTOLOGY_URI}/1.0.0")))

    graph.add(
        (
            ONTOLOGY_URI,
            DCTERMS.title,
            Literal(
                "MathModDB Knowledge Graph of Mathematical Models | MathModDB",
                lang="en",
            ),
        )
    )

    # g.add((ONTOLOGY_URI, DCTERMS.creator, Literal("Katrin Moeller")))  # adjust

    # g.add((ONTOLOGY_URI, DCTERMS.publisher, Literal("Olaf Simons")))  # adjust

    # TODO: select license properly
    # g.add((ONTOLOGY_URI, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))  # CC-BY default

    graph.add((ONTOLOGY_URI, DCTERMS.hasVersion, Literal("1.0.0", datatype=XSD.string)))

    # g.add((ONTOLOGY_URI, OMW["releaseDate"],Literal("2023-01-01", datatype=XSD.date)))  # adjust

    # Optional but recommended
    graph.add(
        (
            ONTOLOGY_URI,
            DCTERMS.description,
            Literal(
                "MathModDB defines a data model with classes (Mathematical Model, Mathematical Expression, Academic Discipline, Research Problem, Quantity (Kind), Computational Task, Scholarly Article), object properties/relations, data properties and annotation properties as an ontology. This ontology is populated with individuals/data from various fields of applied mathematics, making it a knowledge graph",
                lang="en",
            ),
        )
    )

    print("added ontology metadata to graph")

# =============================================================================
# MAIN - EXECUTION ORDER
# =============================================================================
def main():
    g = Graph()

    # namespaces
    g.bind("mathmoddb", OMW)

    # add metadata
    add_ontology_metadata(g)

    # add individuals to graph
    individuals = get_answer_from_endpoint(INDIVIDUALS_QUERY)
    add_individuals_to_graph(individuals, g)

    # add classes to graph
    classes = get_answer_from_endpoint(CLASSES_QUERY)
    classUris = add_classes_to_graph(classes, g)

    # add properties to graph
    properties = get_answer_from_endpoint(PROPERTIES_QUERY)
    uris_of_p983_p989 = add_properties_to_graph(properties, g)

    # add formula data to graph
    formula_data = get_answer_from_endpoint(FORMULA_QUERY)
    add_formula_data_to_graph(formula_data, g, uris_of_p983_p989)

    # add all individual property relations
    individual_property_value = get_answer_from_endpoint(INDIVIDUAL_PROPERTY_VALUE_QUERY)
    add_individual_property_value_triples_to_graph(individual_property_value, g, classUris)

    # Serialize output
    out_dir = BASE_DIR / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = "MathModDB.owl"
    g.serialize(destination=out_dir / output_file, format="pretty-xml")
    print(f"serialized graph to {output_file}")

    # apply formatter
    # ontology-formatter.jar uses the OWL API
    subprocess.run(
        [
            "java",
            "-jar",
            str(BASE_DIR / "ontology-formatter.jar"),
            str(out_dir / "MathModDB.owl"),
            str(out_dir / "MathModDB.owl"),
        ],
        check=True,
    )

if __name__ == "__main__":
    main()
