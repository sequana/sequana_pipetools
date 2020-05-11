# -*- coding: utf-8 -*-
#
#  This file is part of Sequana_pipetools software (Sequana Projetc)
#
#  Copyright (c) 2020 - Sequana Development Team
#
#  File author(s):
#      Thomas Cokelaer <thomas.cokelaer@pasteur.fr>
#
#  Distributed under the terms of the 3-clause BSD license.
#  The full license is in the LICENSE file, distributed with this software.
#
#  website: https://github.com/sequana/sequana
#  documentation: http://sequana.readthedocs.io
#
##############################################################################
import sys
import os

__all__ = ["Colors", "print_version", "error"]


class Colors:
    """

    ::

        color = Colors()
        print(color.failed("msg"))

    """
    PURPLE = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    def failed(self, msg):
        return self.FAIL + msg + self.ENDC

    def bold(self, msg):
        return self.BOLD + msg + self.ENDC

    def purple(self, msg):
        return self.PURPLE + msg + self.ENDC

    def underlined(self, msg):
        return self.UNDERLINE + msg + self.ENDC

    def fail(self, msg):
        return self.FAIL + msg + self.ENDC

    def error(self, msg):
        return self.FAIL + msg + self.ENDC

    def warning(self, msg):
        return self.WARNING + msg + self.ENDC

    def green(self, msg):
        return self.GREEN + msg + self.ENDC

    def blue(self, msg):
        return self.BLUE + msg + self.ENDC



def error(msg, pipeline):
    color = Colors()
    print(color.error("ERROR [sequana.{}]::".format(pipeline) +  msg), flush=True)
    sys.exit(1)


def print_version(name):
    try:
        import pkg_resources
        version = pkg_resources.require("sequana")[0].version
        print("Sequana version used: {}".format(version))
    except Exception as err:
        print(err)
        print("Sequana version used: ?".format(name))

    try:
        import pkg_resources
        version = pkg_resources.require("sequana_pipetools")[0].version
        print("Sequana_pipetools version used: {}".format(version))
    except Exception as err:
        print(err)
        print("Sequana_pipetools version used: ?".format(name))

    try:
        ver = pkg_resources.require("sequana_{}".format(name))[0].version
        print("pipeline sequana_{} version used: {}".format(name, ver))
    except Exception as err:
        print(err)
        print("pipeline sequana_{} version used: ?".format(name))
        sys.exit(1)
    print(Colors().purple("\nHow to help ?\n- Please, consider citing us (see sequana.readthedocs.io)".format(version)))
    print(Colors().purple("- Contribute to the code or documentation"))
    print(Colors().purple("- Fill issues on https://github.com/sequana/sequana/issues/new/choose"))
    print(Colors().purple("- Star us https://github.com/sequana/sequana/stargazers"))



