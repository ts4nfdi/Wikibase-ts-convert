from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, DCTERMS, XSD

import json
import os

# FactGrid SPARQL endpoint
ENDPOINT = "https://database.factgrid.de/sparql"

CACHE_FILE = "resources/fetchresult.json"

# SPARQL query
QUERY = """
SELECT ?OhdAB_ID ?OhdAB_Schluessel ?OhdAB_SchluesselLabel ?Normansetzung ?Weiblich ?Maennlich
       ?OhdAB_01 ?OhdAB_02 ?OhdAB_03 ?OhdAB_04 ?OhdAB_05 ?OhdAB_AB
       ?AnforderungLabel
WHERE {
  SERVICE wikibase:label { bd:serviceParam wikibase:language "de". }
  
  ?OhdAB_Schluessel wdt:P2 wd:Q647777.
  
  OPTIONAL { ?OhdAB_Schluessel wdt:P904 ?OhdAB_ID. }
  OPTIONAL {
    ?OhdAB_Schluessel wdt:P914 ?Normansetzung.
    FILTER((LANG(?Normansetzung)) = "de")
  }
  OPTIONAL { ?OhdAB_Schluessel wdt:P888 ?Weiblich. }
  OPTIONAL { ?OhdAB_Schluessel wdt:P889 ?Maennlich. }

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
LIMIT 10
"""

# Namespaces
OMW = Namespace("https://w3id.org/omw/")

# The ontology URI (choose one)
ONTOLOGY_URI = URIRef("https://w3id.org/omw/ohdab")   # or your preferred URI

def add_ontology_metadata(G: Graph):

    G.add((ONTOLOGY_URI, RDF.type, OMW["Ontology"]))

    # ---- Mandatory Elements ----
    G.add((ONTOLOGY_URI, OMW["ontologyTitle"],
           Literal("Ontology of the historical German-language nomenclature for offices and professions | OhdAB", lang="de")))

    G.add((ONTOLOGY_URI, DCTERMS.creator,
           Literal("Katrin Moeller")))     # adjust

    G.add((ONTOLOGY_URI, DCTERMS.publisher,
           Literal("Olaf Simons")))    # adjust


#TODO: select license properly
    G.add((ONTOLOGY_URI, DCTERMS.license,
           URIRef("https://creativecommons.org/licenses/by/4.0/")))  # CC-BY default

    G.add((ONTOLOGY_URI, OMW["revision"],
           Literal("1.0.0", datatype=XSD.string)))

    G.add((ONTOLOGY_URI, OMW["releaseDate"],
           Literal("2023-01-01", datatype=XSD.date)))   # adjust

    # Optional but recommended
    G.add((ONTOLOGY_URI, DCTERMS.description,
           Literal("Automatically generated terminology from FactGrid OhdAB.", lang="de")))

def run_query(query: str):
    # ---------------------------------------------
    # 1. If file exists → load cached JSON
    # ---------------------------------------------
    if os.path.exists(CACHE_FILE):
        print(f"✔ Loading cached SPARQL result from {CACHE_FILE}")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    # ---------------------------------------------
    # 2. Otherwise → fetch from SPARQL endpoint
    # ---------------------------------------------
    print("↻ Fetching SPARQL result from FactGrid…")

    sparql = SPARQLWrapper(ENDPOINT)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    # ---------------------------------------------
    # 3. Save result to cache file
    # ---------------------------------------------
    os.makedirs("resources", exist_ok=True)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✔ Result saved to {CACHE_FILE}")

    return results

def val(row, key):
    return row.get(key, {}).get("value")


if __name__ == "__main__":

    # Namespaces
    OMW = Namespace("https://w3id.org/omw/")  # adjust if your omw namespace is different
    G = Graph()
    G.bind("omw", OMW)

    results = run_query(QUERY)

    # Print raw JSON
    print("=== Raw JSON ===")
    print(results)

    # Print results in a readable table
    print("\n=== Results ===")
    for row in results["results"]["bindings"]:
        print({k: v.get("value") for k, v in row.items()})
        term_uri = URIRef(val(row, "OhdAB_Schluessel"))

        G.add((term_uri, RDF.type, OMW["term"]))

        if val(row, "Normansetzung"):
            G.add((term_uri, OMW["preferredLabel"],
                   Literal(val(row, "Normansetzung"), lang="de")))

        if val(row, "OhdAB_ID"):
            G.add((term_uri, OMW["altLabel"],
                   Literal(val(row, "OhdAB_ID"), lang="de")))

        # hierarchy relations (broader)
        levels = ["OhdAB_01", "OhdAB_02", "OhdAB_03", "OhdAB_04", "OhdAB_05", "OhdAB_AB"]

        prev_uri = term_uri

        for lvl in levels:
            uri = val(row, lvl)
            if uri:
                lvl_uri = URIRef(uri)

                # add broader relation
                G.add((prev_uri, OMW.broader, lvl_uri))

                # declare the broader term as omw:Term as well
                G.add((lvl_uri, RDF.type, OMW["term"]))

                prev_uri = lvl_uri

    # Save file
    add_ontology_metadata(G)
    G.serialize("OhdAB.ttl", format="turtle")
    print("RDF exported to OhdAB.ttl")
