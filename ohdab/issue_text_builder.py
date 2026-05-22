from pathlib import Path

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

def write_missing_hierarchy_issue_text(classes_without_real_parent: list):
    output_file = "missing_parents_issue_text.txt"
    with open(RESOURCES_DIR / output_file, "w", encoding="utf-8") as f:
        f.write("# Classes without real parent\n\n")
        f.write("The OhdAB ontology contains the following classes, which do not have a parent class except themselves and therefore do not get sorted into the hierarchy:\n\n")

        for uri in classes_without_real_parent:
            f.write(f"- `{uri}`\n")

        f.write("\n\n")
        f.write("cc @1, @2")