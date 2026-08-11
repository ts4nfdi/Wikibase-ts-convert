from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import OWL, RDF, RDFS, DCTERMS, XSD, SDO, FOAF, DOAP
from pathlib import Path
import subprocess
from datetime import date

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

# This query pulls all properties used as qualifier propertys by statements that are targeted by individuals in the
# mathmoddb scope. This query is used to define the qualifier properties.
QUALIFIER_PROPERTIES_QUERY = """
SELECT DISTINCT
    ?property
    ?propertyId
    ?propertyLabel
    ?propertyDescription
WHERE {
    ?individual wdt:P1495 wd:Q6534265 .

    ?baseProperty wikibase:claim ?statementProperty .
    ?individual ?statementProperty ?statement .

    ?property wikibase:qualifier ?qualifierProperty .
    ?statement ?qualifierProperty ?qualifierValue .

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

# This query pulls one row per statement with a qualifier for each individual.
QUALIFIER_QUERY = """
SELECT DISTINCT
    ?individual
    ?property
    ?statementValue
    ?qualifierProperty
    ?qualifierValue
WHERE {
    ?individual wdt:P1495 wd:Q6534265 .

    ?property wikibase:claim ?statementProperty ;
              wikibase:statementProperty ?statementValueProperty .
  
    ?individual ?statementProperty ?statement .

    ?statement ?statementValueProperty ?statementValue .

    ?qualifierProperty wikibase:qualifier ?qualifierPredicate .
  
    # The statement must contain a qualifier property and its value.
    ?statement ?qualifierPredicate ?qualifierValue .
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
    for entry in properties:
        property_uri = URIRef(entry["property"]["value"])

        # P983 and P989 should be added as DatatypeProperties, the rest as AnnotationProperties
        if entry["propertyId"]["value"] in ["P983", "P989"]:
            graph.add((property_uri, RDF.type, OWL.DatatypeProperty))
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


def add_qualifiers_to_graph(qualifier_data, graph):
    for entry in qualifier_data:
        individual = URIRef(entry["individual"]["value"])
        property = URIRef(entry["property"]["value"])
        qualifierProperty = URIRef(entry["qualifierProperty"]["value"])
        qualifierValue, statementValue = (
            URIRef(entry[key]["value"]) if entry[key]["type"] == "uri"
            else Literal(entry[key]["value"], lang="en")
            for key in ["qualifierValue", "statementValue"]
        )

        axiom = BNode()
        graph.add((axiom, RDF.type, OWL.Axiom))
        graph.add((axiom, OWL.annotatedSource, individual))
        graph.add((axiom, OWL.annotatedTarget, statementValue))
        graph.add((axiom, OWL.annotatedProperty, property))
        graph.add((axiom, qualifierProperty, qualifierValue))

    print(f"added {len(qualifier_data)} qualifiers to graph")


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

    # versionIRI and version
    graph.add((ONTOLOGY_URI, OWL.versionIRI, URIRef(f"{ONTOLOGY_URI}2.0.0")))
    graph.add((ONTOLOGY_URI, OWL.versionInfo, Literal("2.0.0", datatype=XSD.string)))

    # title
    graph.add(
        (
            ONTOLOGY_URI,
            DCTERMS.title,
            Literal(
                "MathModDB Knowledge Graph of Mathematical Models",
                lang="en",
            ),
        )
    )

    # label
    graph.add((ONTOLOGY_URI, RDFS.label, Literal("MathModDB Knowledge Graph of Mathematical Models",
                                                 lang="en")))

    # description

    graph.add((ONTOLOGY_URI, DCTERMS.description,
               Literal("MathModDB is a database of mathematical models developed by the Mathematical "
                       "Research Data Initiative (MaRDI). It defines a data model with classes (Mathematical Model, "
                       "Mathematical Formulation, Academic Discipline, Research Problem, Quantity [Kind], Computational "
                       "Task, Publication), object properties/relations, data properties and annotation properties as "
                       "an ontology. This ontology is populated with individuals/data from various fields of applied "
                       "mathematics, making it a knowledge graph. ", lang="en")))

    # abstract
    graph.add((ONTOLOGY_URI, DCTERMS.abstract,
               Literal("MathModDB is a database of mathematical models developed by the Mathematical"
                       " Research Data Initiative (MaRDI). MathModDB defines a data model with classes (Mathematical "
                       "Model, Mathematical Formulation, Research Field, Research Problem, Quantity [Kind], "
                       "Computational Task, Publication), object properties/relations, data properties and annotation"
                       " properties as an ontology. This ontology is populated with individuals/data from various"
                       " fields of applied mathematics, making it a knowledge graph.", lang="en")))

    # homepage
    graph.add((ONTOLOGY_URI, FOAF.homepage, Literal("https://portal.mardi4nfdi.de/wiki/MathModDB",
                                                    lang="en")))

    # issue tracker
    # graph.add((ONTOLOGY_URI, DOAP["bug-database"], URIRef("https://github.com/MaRDI4NFDI/MathModDB/issues")))

    # license
    graph.add((ONTOLOGY_URI, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))

    # bibliographic citation
    graph.add((ONTOLOGY_URI, DCTERMS.bibliographicCitation, Literal("Shehu, A., Schembera, B., Schmidt, B.,"
                                                                " Biedinger, C., Fiedler, J., Reidelbach, M., Koprucki,"
                                                                " T. (2025): MathModDB Ontology and Knowledge Graph for"
                                                                " Mathematical Models", lang="en")))

    # subjects
    # for subject in ["Computer Science", "Mathematics", "Engineering"]:
    #    graph.add((ONTOLOGY_URI, DCTERMS.subject, Literal(subject, lang="en")))

    # issued + modified
    today = date.today()
    graph.add((ONTOLOGY_URI, DCTERMS.issued, Literal(today, datatype=XSD.dateTime)))
    graph.add((ONTOLOGY_URI, DCTERMS.modified, Literal(today, datatype=XSD.dateTime)))

    # see also
    see_also_links = [
        "https://doi.org/10.1007/978-3-031-65990-4_14",
        "https://doi.org/10.1007/978-3-031-81974-2_8",
        "https://doi.org/10.52825/cordi.v1i.255",
    ]

    for link in see_also_links:
        graph.add((ONTOLOGY_URI,RDFS.seeAlso,URIRef(link)))

    # publisher
    graph.add((ONTOLOGY_URI, DCTERMS.publisher, Literal('Mathematical Research Data Initiative (MaRDI,'
                                                        ' https://www.mardi4nfdi.de)', lang="en")))

    # creators

    creator_values = [
        "Aurela Shehu (https://orcid.org/0000-0002-1994-0612), "
        "Weierstrass Institute Berlin for Applied Analysis and Stochastics "
        "(https://ror.org/00h1x4t21, https://isni.org/isni/000000010066936X)",
        "Björn Schembera (https://orcid.org/0000-0003-2860-6621), "
        "Universität Stuttgart "
        "(https://ror.org/04vnq7t77, https://isni.org/isni/0000000419369713)",
        "Burkhard Schmidt (https://orcid.org/0000-0002-9658-499X), "
        "Weierstrass Institute Berlin for Applied Analysis and Stochastics "
        "(https://ror.org/00h1x4t21, https://isni.org/isni/000000010066936X)",
        "Christine Biedinger (https://orcid.org/0009-0002-5082-8386), "
        "Fraunhofer Institute for Industrial Mathematics ITWM "
        "(https://ror.org/019hjw009)",
        "Jochen Fiedler (https://orcid.org/0000-0002-9176-780X), "
        "Fraunhofer Institute for Industrial Mathematics ITWM "
        "(https://ror.org/019hjw009)",
        "Marco Reidelbach (https://orcid.org/0000-0002-1919-1834), "
        "Zuse Institute Berlin "
        "(https://ror.org/02eva5865, https://isni.org/isni/000000011010926X)",
        "Thomas Koprucki (https://orcid.org/0000-0001-6235-9412), "
        "Weierstrass Institute Berlin for Applied Analysis and Stochastics "
        "(https://ror.org/00h1x4t21, https://isni.org/isni/000000010066936X)",
    ]

    for creator in creator_values:
        graph.add(
            (
                ONTOLOGY_URI,
                DCTERMS.creator,
                Literal(creator, lang="en"),
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

    # add properties and qualifier properties to graph
    properties = get_answer_from_endpoint(PROPERTIES_QUERY)
    q_properties = get_answer_from_endpoint(QUALIFIER_PROPERTIES_QUERY)
    all_properties = properties + q_properties
    add_properties_to_graph(all_properties, g)

    # add qualifiers to graph
    qualifier_data = get_answer_from_endpoint(QUALIFIER_QUERY)
    add_qualifiers_to_graph(qualifier_data, g)

    # add all individual property relations
    ipv = get_answer_from_endpoint(INDIVIDUAL_PROPERTY_VALUE_QUERY)
    add_individual_property_value_triples_to_graph(ipv, g, classUris)

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
