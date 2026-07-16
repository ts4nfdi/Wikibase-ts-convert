from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import OWL, RDF, RDFS, DCTERMS, XSD, FOAF, SDO

import json
import os

# Path to folder of this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# resources folder
RESOURCES_DIR = os.path.join(BASE_DIR, "resources")

# FactGrid SPARQL endpoint
ENDPOINT = "https://query.portal.mardi4nfdi.de/sparql"

CACHE_FILE = os.path.join(RESOURCES_DIR, "fetchresult.json")

# Namespaces
OMW = Namespace("https://portal.mardi4nfdi.de/entity/")
# The ontology URI (choose one)
ONTOLOGY_URI = URIRef("https://portal.mardi4nfdi.de/wiki/")

# SPARQL query
# NOTE: If you change the query, delete the caching file "fetchresult.json" to get updated results !!!
QUERY_TEMPLATE = """
SELECT DISTINCT
  ?item
  ?itemLabel
  ?itemDescription
  ?itemDepiction
  ?class
  ?classLabel
  ?classDescription
  ?formulaData
  ?annotatedTarget
  ?linkedTargetItem
  %%OPTIONAL_IDS%%
WHERE {

  ?item wdt:P1495 wd:Q6534265.
  ?item wdt:P31 ?class.
  wd:Q6534265 wdt:P265 ?class.

  OPTIONAL {
    ?item wdt:P989 ?formulaData .

    OPTIONAL {
      ?item p:P983 ?inDefiningFormStatement .
      ?inDefiningFormStatement ps:P983 ?annotatedTarget .
      ?inDefiningFormStatement pq:P984 ?linkedTargetItem .
    }       
  }
  
  %%OPTIONALS%%
  

  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en" .
  }
}
"""

def add_optionals_to_query(queryTemplate, optProperties: dict):
    optionals = ""
    optional_ids = ""

    for k, v in optProperties.items():
        optional_ids += f"?{v} "
        optionals += f"OPTIONAL {{ ?item wdt:{k} ?{v} }} \n"

    print(optionals, optional_ids)

    queryTemplate = queryTemplate.replace("%%OPTIONALS%%", optionals)
    queryTemplate = queryTemplate.replace("%%OPTIONAL_IDS%%", optional_ids)

    return queryTemplate

def get_optional_properties():
    query = """
    SELECT DISTINCT ?property
    WHERE {
      ?item wdt:P1495 wd:Q6534265 .
      ?item ?property ?value .
    }
    """

    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    optionalProperties = []

    for row in results["results"]["bindings"]:
        optionalProperties.append(row["property"]["value"])

    return optionalProperties

def add_ontology_metadata(g: Graph):
    g.add((ONTOLOGY_URI, RDF.type, OWL.Ontology))

    g.add((ONTOLOGY_URI, OWL.versionIRI, URIRef(f"{ONTOLOGY_URI}/1.0.0")))

    # ---- Mandatory Elements ----
    g.add(
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

    g.add((ONTOLOGY_URI, DCTERMS.hasVersion, Literal("1.0.0", datatype=XSD.string)))

    # g.add((ONTOLOGY_URI, OMW["releaseDate"],Literal("2023-01-01", datatype=XSD.date)))  # adjust

    # Optional but recommended
    g.add(
        (
            ONTOLOGY_URI,
            DCTERMS.description,
            Literal(
                "MathModDB defines a data model with classes (Mathematical Model, Mathematical Expression, Academic Discipline, Research Problem, Quantity (Kind), Computational Task, Scholarly Article), object properties/relations, data properties and annotation properties as an ontology. This ontology is populated with individuals/data from various fields of applied mathematics, making it a knowledge graph",
                lang="en",
            ),
        )
    )


def run_query(query: str, cache: bool):
    # ---------------------------------------------
    # 1. If file exists → load cached JSON
    # ---------------------------------------------
    if cache and os.path.exists(CACHE_FILE):
        print(f"✔ Loading cached SPARQL result from {CACHE_FILE}")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---------------------------------------------
    # 2. Otherwise → fetch from SPARQL endpoint
    # ---------------------------------------------
    print("↻ Fetching SPARQL result…")

    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    # ---------------------------------------------
    # 3. Save result to cache file
    # ---------------------------------------------
    os.makedirs(RESOURCES_DIR, exist_ok=True)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✔ Result saved to {CACHE_FILE}")

    return results


def addPropertyData(g: Graph):
    query = """
    SELECT ?property ?propertyLabel ?propertyDescription WHERE {
      VALUES ?property { wd:P983 wd:P984 wd:P989 }

      SERVICE wikibase:label {
        bd:serviceParam wikibase:language "en" .
      }
    }
    """

    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    results = results["results"]["bindings"]
    for result in results:
        property = URIRef(result["property"]["value"])

        # save property in global PROPERTIES dict
        key = result["property"]["value"].split("/")[-1]
        # PROPERTIES[key] = property

        if key == "P984":
            g.add((property, RDF.type, OWL.AnnotationProperty))
        else:
            g.add((property, RDF.type, OWL.DatatypeProperty))

        if "propertyLabel" in result:
            propertyLabel = Literal(result["propertyLabel"]["value"], lang="en")
            g.add((property, RDFS.label, propertyLabel))
        if "propertyDescription" in result:
            propertyDescription = Literal(
                result["propertyDescription"]["value"], lang="en"
            )
            g.add((property, SDO.description, propertyDescription))

        # save property in global PROPERTIES dict
        # key = result["property"]["value"].split("/")[-1]
        # PROPERTIES[key] = property

def get_uri_for_property(property):
    return URIRef(f"https://portal.mardi4nfdi.de/entity/{property}")


def create_as_terms(g, results, optProperties: dict):
    for uri, entry in results.items():

        term_uri = URIRef(uri)

        # g.add((term_uri, RDF.type, OMW["term"]))
        g.add((term_uri, RDF.type, OWL.NamedIndividual))

        if "itemLabel" in entry:
            g.add((term_uri, RDFS.label, Literal(entry["itemLabel"], lang="en")))

        if "itemDescription" in entry:
            g.add(
                (
                    term_uri,
                    SDO.description,
                    Literal(entry["itemDescription"], lang="en"),
                )
            )

        if "itemDepiction" in entry:
            depictions = entry["itemDepiction"]
            if not isinstance(depictions, list):
                depictions = [depictions]
            g.add((term_uri, FOAF.depiction, Literal(json.dumps(depictions)[2:-2])))


        for k, v in optProperties.items():
            if v in entry:
                g.add((term_uri, get_uri_for_property(k) , Literal(entry[v], lang="en")))

        # hierarchy relations (broader)

        if "class" in entry:
            class_uri = URIRef(entry["class"])
            # add relation
            g.add((term_uri, RDF.type, class_uri))

            # add class
            g.add((class_uri, RDF.type, RDFS.Class))

            if "classLabel" in entry:
                g.add((class_uri, RDFS.label, Literal(entry["classLabel"], lang="en")))

            if "classDescription" in entry:
                g.add(
                    (
                        class_uri,
                        SDO.description,
                        Literal(entry["classDescription"], lang="en"),
                    )
                )
        # add defining formula
        if "formulaData" in entry:
            g.add(
                (
                    term_uri,
                    get_uri_for_property("P989"),
                    Literal(entry["formulaData"]),
                )
            )

        # add in defining formula
        if "annotatedTargetsAndItems" in entry:
            for pair in entry["annotatedTargetsAndItems"]:

                g.add((term_uri, get_uri_for_property("P983"), Literal(pair["annotatedTarget"])))
                axiom = BNode()
                g.add((axiom, RDF.type, OWL.Axiom))
                g.add((axiom, OWL.annotatedSource, term_uri))
                g.add((axiom, OWL.annotatedTarget, Literal(pair["annotatedTarget"])))
                g.add((axiom, OWL.annotatedProperty, get_uri_for_property("P983")))
                g.add((axiom, get_uri_for_property("P984"), Literal(pair["linkedTargetItem"])))

        #    uri = val(entry, lvl)
        #    if uri:
        #        lvl_uri = URIRef(uri)

        # add broader relation
        # g.add((prev_uri, OMW.broader, lvl_uri))

        # declare the broader term as omw:Term as well
        # g.add((lvl_uri, RDF.type, OMW["term"]))

        # prev_uri = lvl_uri


def create_as_classes(g, results):
    for entry in results.values():

        # Use DE URI (same as EN)
        class_uri = URIRef(entry["OhdAB_Schluessel_de"])

        g.add((class_uri, RDF.type, RDFS.Class))

        # -------------------------
        # Class labels
        # -------------------------
        if "OhdAB_SchluesselLabel_de" in entry:
            g.add(
                (
                    class_uri,
                    RDFS.label,
                    Literal(entry["OhdAB_SchluesselLabel_de"], lang="de"),
                )
            )

        if "OhdAB_SchluesselLabel_en" in entry:
            g.add(
                (
                    class_uri,
                    RDFS.label,
                    Literal(entry["OhdAB_SchluesselLabel_en"], lang="en"),
                )
            )

        # -------------------------
        # Gender-specific altLabels (P888 / P889)
        # -------------------------

        if "Weiblich_de" in entry:
            G.add((class_uri, RDFS.label, Literal(entry["Weiblich_de"], lang="de")))

        if "Maennlich_de" in entry:
            G.add((class_uri, RDFS.label, Literal(entry["Maennlich_de"], lang="de")))

        if "Weiblich_en" in entry:
            G.add((class_uri, RDFS.label, Literal(entry["Weiblich_en"], lang="en")))

        if "Maennlich_en" in entry:
            G.add((class_uri, RDFS.label, Literal(entry["Maennlich_en"], lang="en")))

        # -------------------------
        # Hierarchy
        # -------------------------
        levels = [
            "OhdAB_01",
            "OhdAB_02",
            "OhdAB_03",
            "OhdAB_04",
            "OhdAB_05",
            "OhdAB_AB",
        ]

        prev_uri = class_uri

        for lvl in levels:
            key_de = f"{lvl}_de"
            key_label_de = f"{lvl}Label_de"
            key_label_en = f"{lvl}Label_en"

            if key_de in entry:
                lvl_uri = URIRef(entry[key_de])

                g.add((prev_uri, RDFS.subClassOf, lvl_uri))
                g.add((lvl_uri, RDF.type, RDFS.Class))

                if key_label_de in entry:
                    g.add(
                        (lvl_uri, RDFS.label, Literal(entry[key_label_de], lang="de"))
                    )

                if key_label_en in entry:
                    g.add(
                        (lvl_uri, RDFS.label, Literal(entry[key_label_en], lang="en"))
                    )

                prev_uri = lvl_uri


def prepare_results(data):
    final = {}
    pair_keys = ("linkedTargetItem", "annotatedTarget")

    for row in data["results"]["bindings"]:
        key = row["item"]["value"]

        entry = final.setdefault(key, {})

        for k, v in row.items():
            if k in pair_keys:
                continue

            if not k in entry:
                entry[k] = v["value"]

        if "annotatedTarget" in row:
            pair = {pk: row[pk]["value"] for pk in pair_keys}
            entry.setdefault("annotatedTargetsAndItems", []).append(pair)
    final_file = os.path.join(RESOURCES_DIR, "query.json")

    with open(final_file, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    return final

def main():
    # Namespaces
    G = Graph()
    G.bind("mathmoddb", OMW)

    addPropertyData(G)

    optionalProperties = {
        "P558": "namedAfter",
        "P1459": "description",
        "P1656": "discretizedBy",
        "P1684": "specializedBy",
        "P1690": "relatedUrl",
    }

    query = add_optionals_to_query(QUERY_TEMPLATE, optionalProperties)

    print(query)

    # results = run_query(QUERY)
    # results_de = run_query(QUERY_TEMPLATE.replace("%LANG%", "de"), False)
    results_en = run_query(query.replace("%LANG%", "en"), False)
    results = prepare_results(results_en)

    # Print raw JSON
    print("=== Raw JSON ===")

    print("\n=== Results ===")
    create_as_terms(G, results, optionalProperties)
    # create_as_classes(G, results)

    # Save file
    add_ontology_metadata(G)
    OUT_DIR = os.path.join(BASE_DIR, "out")
    os.makedirs(OUT_DIR, exist_ok=True)
    G.serialize(os.path.join(OUT_DIR, "MathModDB.owl"), format="xml")
    print("RDF exported to MathModDB.ttl")


if __name__ == "__main__":
    main()
