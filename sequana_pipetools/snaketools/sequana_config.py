#
#  This file is part of Sequana software
#
#  Copyright (c) 2016-2021 - Sequana Dev Team (https://sequana.readthedocs.io)
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  Website:       https://github.com/sequana/sequana
#  Documentation: http://sequana.readthedocs.io
#  Contributors:  https://github.com/sequana/sequana/graphs/contributors
##############################################################################
import os
import json
import shutil
import warnings

from easydev import AttrDict, TempFile
from urllib.request import urlretrieve
import ruamel.yaml

import colorlog
logger = colorlog.getLogger(__name__)


class SequanaConfig:
    """Reads YAML config file and ease access to its contents

    This can also be used to check the validity of the config file

    ::

        >>> sc = SequanaConfig(config)
        >>> sc.config.pattern == "*.fastq.gz"
        True

    Empty strings in a config are interpreted as None but SequanaConfig will
    replace  None with empty strings, which is probably what was expected from
    the user. Similarly, in snakemake when settings the config file, one
    can override a value with a False but this is interepted as "False"
    This will transform back the "True" into True.

    Another interest concerns the automatic expansion of the path to directories
    and files starting with the special ~ (tilde) character, that are expanded
    transparently.


    """

    def __init__(self, data=None, converts_none_to_str=True):
        """Could be a JSON or a YAML file

        :param str data: Dictionnary or filename to a config file in json or YAML format.

        SEQUANA config files must have some specific fields::

            input_directory
        """
        # Create a dummy YAML code to hold data in case the input is a json
        # or a dictionary structure. We use a CommentedMap that works like
        # a dictionary. Be aware that the update method may lose the comments
        # if yaml dictionary not updated correctly.
        if data:
            try:
                self.config = AttrDict(**data)
                self._yaml_code = ruamel.yaml.comments.CommentedMap(self.config.copy())
            except TypeError:
                if hasattr(data, 'config'):
                    self.config = AttrDict(**data.config)
                    self._yaml_code = ruamel.yaml.comments.CommentedMap(self.config.copy())
                else:
                    self.config = self._read_file(data)
        else:
            self.config = AttrDict()
            self._yaml_code = ruamel.yaml.comments.CommentedMap()
        self.cleanup_config()

    def _read_file(self, data):
        """Read yaml or json file"""
        try:
            is_yml = data.endswith(('.yaml', '.yml'))
        except AttributeError:
            raise IOError("Data param does not have the good format. It's a filename or a dict")

        if os.path.exists(data):
            yaml = ruamel.yaml.YAML()
            if is_yml:
                with open(data, "r") as fh:
                    self._yaml_code = yaml.load(fh.read())
            else:
                # read a JSON
                with open(data, "r") as fh:
                    self._yaml_code = yaml.load(json.dumps(json.loads(fh.read())))
        else:
            raise FileNotFoundError(f"input string must be an existing file {data}")
        return AttrDict(**self._yaml_code.copy())

    def save(self, filename="config.yaml", cleanup=True):
        """Save the yaml code in _yaml_code with comments"""
        # This works only if the input data was a yaml
        if cleanup:
            self.cleanup()  # changes the config and yaml_code to remove %()s

        # get the YAML formatted code and save it
        yaml = ruamel.yaml.YAML() 
        yaml.default_style = ""
        yaml.indent = 4 
        yaml.block_seq_indent = 4

        with open(filename, 'w') as fh:
            yaml.dump(self._yaml_code, fh)

    def _recursive_update(self, target, data):
        # recursive update of target using data. Both target and data must have
        # same items

        # !! essential to use the update() method of the dictionary otherwise
        # comments are lost

        for key, value in data.items():
            if isinstance(value, dict):
                target.update({key: self._recursive_update(target[key], value)})
            elif isinstance(value, list):
                try:
                    # if input is a yaml
                    new = ruamel.yaml.comments.CommentedSeq(value)
                    new.ca._items = target[key].ca._items.copy()
                    target[key] = new
                except Exception:
                    target[key] = value
            elif isinstance(key, (int, float, str)):
                if key in target.keys():
                    value = data[key]
                    target.update({key: value})
                else:
                    logger.warning("This %s key was not in the original config" " but added" % key)
                    value = data[key]
                    target.update({key: value})
            else:
                raise NotImplementedError(
                    "Only dictionaries and list are authorised in the input configuration file."
                    f" Key/value that cause error are {key}/{value}"
                )
        return target

    def _update_yaml(self):
        self._recursive_update(self._yaml_code, self.config)

    def _update_config(self):
        # probably useless function now since we do not use json as input
        # anymore
        self._recursive_update(self.config, self._yaml_code)

    def _recursive_cleanup(self, d):
        # expand the tilde (see https://github.com/sequana/sequana/issues/486)
        # remove the %() templates
        for key, value in d.items():
            try:
                self._recursive_cleanup(value)
            except AttributeError:
                if value is None:
                    d[key] = ""
                elif isinstance(value, str):
                    if value.startswith("%("):
                        d[key] = None
                    else:
                        d[key] = value.strip()
                    # https://github.com/sequana/sequana/issues/486
                    if key.endswith("_directory") and value.startswith("~/"):
                        d[key] = os.path.expanduser(value)
                    if key.endswith("_file") and value.startswith("~/"):
                        d[key] = os.path.expanduser(value)

    def cleanup_config(self):
        self._recursive_cleanup(self.config)
        # self._update_yaml()

    def cleanup(self):
        """Remove template elements and change None to empty string."""
        self._recursive_cleanup(self._yaml_code)
        self._update_config()

    def copy_requirements(self, target):
        """Copy files to run the pipeline

        If a requirement file exists, it is copied in the target directory.
        If not, it can be either an http resources or a sequana resources.
        """

        if "requirements" in self._yaml_code.keys():
            for requirement in self._yaml_code["requirements"]:
                if os.path.exists(requirement):
                    try:
                        shutil.copy(requirement, target)
                    except shutil.SameFileError:
                        pass  # the target and input may be the same
                elif requirement.startswith("http"):
                    logger.info(f"This file {requirement} will be needed. Downloading")
                    output = requirement.split("/")[-1]
                    urlretrieve(requirement, filename=os.sep.join((target, output)))

    def check_config_with_schema(self, schemafile):
        """Check the config file with respect to a schema file

        Sequana pipelines should have a schema file in the Module.

        """
        from pykwalify.core import Core

        # causes issue with ruamel.yaml 0.12.13. Works for 0.15
        warnings.simplefilter("ignore", ruamel.yaml.error.UnsafeLoaderWarning)
        try:
            # open the config and the schema file
            with TempFile(suffix=".yaml") as fh:
                self.save(fh.name)
                c = Core(source_file=fh.name, schema_files=[schemafile])
                c.validate()
        except Exception as err:
            print(err)
            return False