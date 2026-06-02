from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, DCTERMS, XSD, SKOS
from . import issue_text_builder

import time
import json
import os

# Path to folder of this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Resource folder
RESOURCES_DIR = os.path.join(BASE_DIR, "resources")

# FactGrid SPARQL endpoint
ENDPOINT = "https://database.factgrid.de/sparql"

CACHE_FILE = os.path.join(RESOURCES_DIR, "fetchresult.json")

# SPARQL query
# NOTE: If you change the query, delete the caching file "resources/fetchresult.json" to get updated results !!!
QUERY_TEMPLATE = """
SELECT ?OhdAB_ID ?OhdAB_Schluessel ?OhdAB_SchluesselLabel ?Normansetzung
       ?Weiblich ?Maennlich
       ?OhdAB_01 ?OhdAB_01Label
       ?OhdAB_02 ?OhdAB_02Label
       ?OhdAB_03 ?OhdAB_03Label
       ?OhdAB_04 ?OhdAB_04Label
       ?OhdAB_05 ?OhdAB_05Label
       ?OhdAB_AB ?OhdAB_ABLabel
       ?AnforderungLabel
WHERE {
  SERVICE wikibase:label { bd:serviceParam wikibase:language "%LANG%". }

  ?OhdAB_Schluessel wdt:P2 wd:Q647777.
  OPTIONAL { ?OhdAB_Schluessel wdt:P904 ?OhdAB_ID. }

  OPTIONAL {
    ?OhdAB_Schluessel wdt:P914 ?Normansetzung.
    FILTER (LANG(?Normansetzung) = "%LANG%")
  }

  
  OPTIONAL {
    ?OhdAB_Schluessel wdt:P888 ?Weiblich.
    FILTER (LANG(?Weiblich) = "%LANG%")
  }
    
  OPTIONAL {
    ?OhdAB_Schluessel wdt:P889 ?Maennlich.
    FILTER (LANG(?Maennlich) = "%LANG%")
  }

  OPTIONAL {
    ?OhdAB_Schluessel wdt:P1007 ?OhdAB_01.
    ?OhdAB_01 wdt:P1007 ?OhdAB_02.
    ?OhdAB_02 wdt:P1007 ?OhdAB_03.
    ?OhdAB_03 wdt:P1007 ?OhdAB_04.
    ?OhdAB_04 wdt:P1007 ?OhdAB_05.
    ?OhdAB_05 wdt:P1007 ?OhdAB_AB.
  }

  OPTIONAL { ?OhdAB_Schluessel wdt:P911 ?Anforderung. }
}
ORDER BY (?OhdAB_ID)
"""

# Namespaces
OMW = Namespace("https://database.factgrid.de")


# The ontology URI (choose one)
ONTOLOGY_URI = URIRef("https://database.factgrid.de/wiki/FactGrid:OhdAB-Datenbank")


def add_ontology_metadata(g: Graph):
    g.add((ONTOLOGY_URI, RDF.type, OWL.Ontology))

    g.add((ONTOLOGY_URI, OWL.versionIRI, URIRef(f"{ONTOLOGY_URI}/1.0.0")))

    # ---- Mandatory Elements ----
    g.add((ONTOLOGY_URI, DCTERMS.title,
           Literal("Ontologie der historischen, deutschsprachigen Amts- und Berufsbezeichnungen | OhdAB",
                   lang="de")))
    g.add((ONTOLOGY_URI, DCTERMS.title,
           Literal("Ontology of the historical German-language nomenclature for offices and professions "
                   "| OhdAB", lang="en")))

    g.add((ONTOLOGY_URI, DCTERMS.creator,
           Literal("Katrin Moeller")))  # adjust

    g.add((ONTOLOGY_URI, DCTERMS.publisher,
           Literal("Olaf Simons")))  # adjust

    # TODO: select license properly
    g.add((ONTOLOGY_URI, DCTERMS.license,
           URIRef("https://creativecommons.org/licenses/by/4.0/")))  # CC-BY default

    g.add((ONTOLOGY_URI, DCTERMS.hasVersion,
           Literal("1.0.0", datatype=XSD.string)))

    g.add((ONTOLOGY_URI, DCTERMS.date,
           Literal("2023-01-01", datatype=XSD.date)))  # adjust

    # Optional but recommended
    g.add((ONTOLOGY_URI, DCTERMS.description,
           Literal(
               "Diese Version der Ontologie der historischen, deutschsprachigen Amts- und "
               "Berufsbezeichnungen (OhdAB) wurde über ein Skript automatisch aus FactGrid generiert.",
               lang="de")))
    g.add((ONTOLOGY_URI, DCTERMS.description,
           Literal(
               "This version of the historical German-language nomenclature for offices and professions "
               "(OhdAB) was automatically generated via a script from FactGrid.",
               lang="en")))

    # additional properties from FactGrid
    g.add((URIRef("https://database.factgrid.de/wiki/Property:P888"), RDF.type, OWL.ObjectProperty))
    g.add((URIRef("https://database.factgrid.de/wiki/Property:P888"), RDFS.label,
           Literal("Weibliche Form des Labels", lang="de")))
    g.add((URIRef("https://database.factgrid.de/wiki/Property:P888"), RDFS.label,
           Literal("Female form of label", lang="en")))

    g.add((URIRef("https://database.factgrid.de/wiki/Property:P889"), RDF.type, OWL.ObjectProperty))
    g.add((URIRef("https://database.factgrid.de/wiki/Property:P889"), RDFS.label,
           Literal("Männliche Form des Labels", lang="de")))
    g.add((URIRef("https://database.factgrid.de/wiki/Property:P889"), RDFS.label,
           Literal("Male form of label", lang="en")))

    g.add((ONTOLOGY_URI, DCTERMS.isVersionOf,
           URIRef("https://database.factgrid.de/wiki/Item:Q518459")))


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
    print("↻ Fetching SPARQL result from FactGrid…")

    MAX_ATTEMPTS = 5
    REQUEST_TIMEOUT = 75
    WAIT_BETWEEN_REQUESTS = 30

    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    sparql.setTimeout(REQUEST_TIMEOUT)
    for i in range(5):
        try:
            print(f"SPARQL request attempt {i+1}/{MAX_ATTEMPTS}")
            results = sparql.query().convert()
            break
        except Exception as e:
            print(f"SPARQL request failed with error: {e}")
            if i+1 < MAX_ATTEMPTS:
                print(f"Waiting {WAIT_BETWEEN_REQUESTS} seconds before retrying")
                time.sleep(WAIT_BETWEEN_REQUESTS)
            else:
                raise RuntimeError(f"SPARQL request failed after {MAX_ATTEMPTS} attempts") from e

    # ---------------------------------------------
    # 3. Save result to cache file
    # ---------------------------------------------
    os.makedirs(RESOURCES_DIR, exist_ok=True)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✔ Result saved to {CACHE_FILE}")

    return results


def val(row, key):
    return row.get(key, {}).get("value")


def create_as_terms(g, results):
    for row in results["results"]["bindings"]:
        # print({k: v.get("value") for k, v in row.items()})
        term_uri = URIRef(val(row, "OhdAB_Schluessel"))

        g.add((term_uri, RDF.type, OMW["term"]))

        if val(row, "Normansetzung"):
            g.add((term_uri, OMW["preferredLabel"],
                   Literal(val(row, "Normansetzung"), lang="de")))

        if val(row, "OhdAB_ID"):
            g.add((term_uri, OMW["altLabel"],
                   Literal(val(row, "OhdAB_ID"), lang="de")))

        # hierarchy relations (broader)
        levels = ["OhdAB_01", "OhdAB_02", "OhdAB_03", "OhdAB_04", "OhdAB_05", "OhdAB_AB"]

        prev_uri = term_uri

        for lvl in levels:
            uri = val(row, lvl)
            if uri:
                lvl_uri = URIRef(uri)

                # add broader relation
                g.add((prev_uri, OMW.broader, lvl_uri))

                # declare the broader term as omw:Term as well
                g.add((lvl_uri, RDF.type, OMW["term"]))

                prev_uri = lvl_uri


def create_as_classes(g, merged_results):
    classes_without_real_parent = []

    for entry in merged_results.values():

        # Use DE URI (same as EN)
        class_uri = URIRef(entry["OhdAB_Schluessel_de"])

        g.add((class_uri, RDF.type, RDFS.Class))

        # -------------------------
        # Class labels
        # -------------------------
        if "OhdAB_SchluesselLabel_de" in entry:
            g.add((class_uri, RDFS.label,
                   Literal(entry["OhdAB_SchluesselLabel_de"], lang="de")))

        if "OhdAB_SchluesselLabel_en" in entry:
            g.add((class_uri, RDFS.label,
                   Literal(entry["OhdAB_SchluesselLabel_en"], lang="en")))

        # -------------------------
        # Gender-specific altLabels (P888 / P889)
        # -------------------------

        if "Weiblich_de" in entry:
            g.add((class_uri, SKOS.altLabel,
                   Literal(entry["Weiblich_de"], lang="de")))

        if "Maennlich_de" in entry:
            g.add((class_uri, SKOS.altLabel,
                   Literal(entry["Maennlich_de"], lang="de")))

        if "Weiblich_en" in entry:
            g.add((class_uri, SKOS.altLabel,
                   Literal(entry["Weiblich_en"], lang="en")))

        if "Maennlich_en" in entry:
            g.add((class_uri, SKOS.altLabel,
                   Literal(entry["Maennlich_en"], lang="en")))

        # -------------------------
        # Hierarchy
        # -------------------------
        levels = ["OhdAB_01", "OhdAB_02", "OhdAB_03", "OhdAB_04", "OhdAB_05", "OhdAB_AB"]

        prev_uri = class_uri
        has_real_parent = False

        for lvl in levels:
            key_de = f"{lvl}_de"
            key_label_de = f"{lvl}Label_de"
            key_label_en = f"{lvl}Label_en"

            if key_de in entry:
                lvl_uri = URIRef(entry[key_de])
                # this only gets triggered if the class has a parent different from itself
                if not (prev_uri == lvl_uri):
                    has_real_parent = True
                g.add((prev_uri, RDFS.subClassOf, lvl_uri))
                g.add((lvl_uri, RDF.type, RDFS.Class))

                if key_label_de in entry:
                    g.add((lvl_uri, RDFS.label,
                           Literal(entry[key_label_de], lang="de")))

                if key_label_en in entry:
                    g.add((lvl_uri, RDFS.label,
                           Literal(entry[key_label_en], lang="en")))

                prev_uri = lvl_uri

        if not has_real_parent:
            classes_without_real_parent.append(class_uri)

    if classes_without_real_parent:
        print("There are classes which do not have a parent class (except their own)")
        issue_text_builder.write_missing_parents_issue_text(classes_without_real_parent)

def merge_results(results_de, results_en):
    merged = {}

    def add_row(row, lang):
        key = row["OhdAB_Schluessel"]["value"]
        entry = merged.setdefault(key, {})
        for k, v in row.items():
            entry[f"{k}_{lang}"] = v["value"]

    for row in results_de["results"]["bindings"]:
        add_row(row, "de")

    for row in results_en["results"]["bindings"]:
        add_row(row, "en")

    return merged

def main():
    # Namespaces
    G = Graph()
    G.bind("ohdab", "https://database.factgrid.de/entity/")
    G.bind("ohdab-prop", "https://database.factgrid.de/wiki/Property:")

    # results = run_query(QUERY)
    results_de = run_query(QUERY_TEMPLATE.replace("%LANG%", "de"), False)
    results_en = run_query(QUERY_TEMPLATE.replace("%LANG%", "en"), False)
    results = merge_results(results_de, results_en)

    # Print raw JSON
    print("=== Raw JSON ===")
    print(results)

    print("\n=== Results ===")
    # create_as_terms(G, results)
    create_as_classes(G, results)

    # Save file
    add_ontology_metadata(G)
    OUT_DIR = os.path.join(BASE_DIR, "out")
    os.makedirs(OUT_DIR, exist_ok=True)
    G.serialize(os.path.join(OUT_DIR, "OhdAB.ttl"), format="turtle")
    print("RDF exported to OhdAB.ttl")


if __name__ == "__main__":
    main()
