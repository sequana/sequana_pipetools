import sys
import os
import argparse
import shutil
from subprocess import check_call
import subprocess

__all__ = ['Complete']


class Options(argparse.ArgumentParser):
    def __init__(self, prog="sequana_completion"):
        usage = """
    sequana_completion --name rnaseq
    sequana_completion --name all
    """

        super(Options, self).__init__(usage=usage, prog=prog, 
            description="""This tool creates completion script for sequana
pipelines. Each pipeline has its own in .config/sequana/pipelines that you can
source at your convenience""",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        self.add_argument("--force", action="store_true", 
            help="""overwrite files in sequana config pipeline directory""")
        self.add_argument("--name",  type=str,
            help="""Name of a pipelines for which you wish to 
            create the completion file. Set to a valid name ror to create all
scripts, use --name all """)


class Complete():

    # KEEP '#version:' on first line as it it since it is used in
    # sequana/pipeline_common.py right now
    setup = """#version: {version}
function _mycomplete_()
{{
    local cur prev opts
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    opts="{options}"
    case "${{prev}}" in
    """

    teardown = """
        #;;
    esac
    #if [[ ${{cur}} == -* ]] ; then
        COMPREPLY=( $(compgen -W "${{opts}}" -- ${{cur}}) )
        return 0
    #fi

}}
#complete -d -X '.[^./]*' -F _mycomplete_ sequana_{pipeline_name}
complete  -F _mycomplete_ sequana_{pipeline_name}
    """

    def __init__(self, pipeline_name):
        self._set_pipeline_name(pipeline_name)

    def _get_pipeline_name(self):
        return self._pipeline_name

    def _set_pipeline_name(self, name):
        self._pipeline_name = name
        self._init_config_file()
        self._init_version()
    pipeline_name = property(_get_pipeline_name, _set_pipeline_name)

    def save_completion_script(self):
        config_path = self.config_path
        pipeline_name = self.pipeline_name

        output_filename = f"{config_path}/{pipeline_name}.sh"

        arguments = self.get_arguments()

        with open(output_filename, "w") as fout:
            fout.write(self.setup.format(version=self.pipeline_version, 
                                         options=" ".join(arguments)))
            for action in self._actions:
                option_name = action.option_strings[0]
                if action.choices:
                    option_choices = " ".join(action.choices )
                    fout.write(self.set_option_with_choice(option_name, option_choices))
                elif option_name.endswith("directory"):
                    fout.write(self.set_option_directory(option_name))
            fout.write(self.teardown.format(pipeline_name=self.pipeline_name))

    def _init_config_file(self):
        # do not import sequana, save time, let us use easydev
        from easydev import CustomConfig
        configuration = CustomConfig("sequana", verbose=False)
        sequana_config_path = configuration.user_config_dir
        path = sequana_config_path + os.sep + "pipelines"
        if os.path.exists(path):
            pass
        else:
            os.mkdir(path)
        self.config_path = path
        return path

    def _init_version(self):
        import importlib
        pname = self.pipeline_name
        mod = importlib.import_module('sequana_pipelines.{}'.format(pname))
        mod = importlib.import_module('sequana_pipelines.{}.main'.format(pname))
        module = sys.modules['sequana_pipelines.{}'.format(self.pipeline_name)]
        version = module.version
        self.pipeline_version = version

    def get_arguments(self):
        import importlib
        pname = self.pipeline_name
        mod = importlib.import_module('sequana_pipelines.{}'.format(pname))
        mod = importlib.import_module('sequana_pipelines.{}.main'.format(pname))
        module = sys.modules['sequana_pipelines.{}'.format(self.pipeline_name)]

        main = module.__getattribute__('main')
        opt = main.Options()
        to_exclude = ["-h", "--help"]
        self._actions = [a for a in opt._actions if a.option_strings[0] not in
to_exclude]
        arguments = [a.option_strings[0] for a in self._actions]
        return arguments

    def set_option_with_choice(self, option_name, option_choices):
        data =  f"""
            {option_name})
                local choices="{option_choices}"
                COMPREPLY=( $(compgen -W "${{choices}}" -- ${{cur}}) )
                return 0
                ;;"""
        return data

    def set_option_directory(self, option_name):
        data = f"""
            {option_name})
                xpat=".[!.]*"
                COMPREPLY=( $(compgen -X "${{xpat}}" -d ${{cur}}) )
                return 0
                ;;"""
        return data


def main(args=None):

    if args is None:
        args = sys.argv[:]

    user_options = Options()

    # If --help or no options provided, show the help
    if len(args) == 1:
        user_options.parse_args(["prog", "--help"])
    else:
       options = user_options.parse_args(args[1:])

    names = []
    if options.name == "all":
        import pkgutil
        import sequana_pipelines
        for ff, module_name, valid in pkgutil.iter_modules(sequana_pipelines.__path__):
            names.append(module_name)
    else:
        names = [options.name]

    if options.force is False:
        msg = ("This will replace files in ./config/sequana/pipelines. "
            "Do you want to proceed y/n: ")
        choice = input(msg)
    else:
        choice = "y"

    if choice == "y":
        print("Please source the files using:: \n")
        for name in names:
            c = Complete(name)
            c.save_completion_script()
            print("source ~/.config/sequana/pipelines/{}.sh".format(name))
        print("\nto activate the completion")
    else:
        print("Stopping creation of completion scripts")


if __name__ == "__main__":
    main()

