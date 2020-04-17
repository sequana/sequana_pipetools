import os
from subprocess import check_call


def init():
    # do not import sequana, save time, let us use easydev
    from easydev import CustomConfig
    configuration = CustomConfig("sequana", verbose=False)
    sequana_config_path = configuration.user_config_dir

    path = sequana_config_path + os.sep + "pipelines"
    if os.path.exists(path):
        pass
    else:
        os.mkdir(path)
    return path

def complete_rnaseq():
    pathname = init()
    from sequana_pipelines.rnaseq import main
    opt = main.Options()
    arguments = [a.option_strings[0] for a in opt._actions]
    arguments = [x for x in arguments if x not in ["-h", "--help"]]
    with open(pathname + os.sep + "rnaseq.sh", "w") as fout:
        fout.write("complete -W '{}' sequana_rnaseq".format(" ".join(arguments)) )

def main():
    complete_rnaseq()


if __name__ == "__main__":
    complete_rnaseq()
