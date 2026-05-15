from pipelines.mathmod.mathmod_pipeline import main as mathmod_pipeline
from pipelines.ohdab.ohdab_pipeline import main as ohdab_pipeline
import sys
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def get_mathmod():
    return mathmod_pipeline()


def get_ohdab():
    return ohdab_pipeline()

def get_all(pipelines: dict):
    for pipe in pipelines:
        print("Executing " + pipe + " pipeline")
        pipelines[pipe]()
    return


def main(args):
    pipelines = {
        "mathmod": get_mathmod,
        "ohdab": get_ohdab
    }
    # if no argument was passed run all pipelines
    if len(args) == 1:
        get_all(pipelines)
        return
    if len(args) == 2:
        # make input case-insensitive
        user_input = args[1].strip().casefold()

        if user_input == "remove":
            # looks in each ontology folder if an "out" folder exists, if yes removes it and its content
            pipelines_folder = BASE_DIR / "pipelines"
            for subfolder in pipelines_folder.iterdir():
                if subfolder.is_dir():
                    for folder_name in ["out", "resources"]:
                        folder = subfolder / folder_name
                        if folder.exists() and folder.is_dir():
                            shutil.rmtree(folder)
            # returns only if second argument has the value remove
            return

        elif user_input == "all":
            get_all(pipelines)
            return

    # iterates over all arguments and looks if valid pipeline and if pipeline was already executed
    already_executed = []
    for arg in args[1:]:
        # make input case-insensitive
        arg = arg.strip().casefold()
        if arg in pipelines and arg not in already_executed:
            already_executed.append(arg)
            print("Executing " + arg + " pipeline")
            pipelines[arg]()
        else:
            print("Unknown ontology: " + arg)
    return


if __name__ == "__main__":
    main(sys.argv)
