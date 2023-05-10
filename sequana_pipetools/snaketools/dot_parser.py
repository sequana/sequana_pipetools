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
import re


class DOTParser:
    """Utility to manipulate the dot file returned by Snakemake

    This class is used in the *dag* and *rulegraph* rules used in the
    snakemake pipeline. The input must be a dag/rulegraph created by snakemake.

    Consider this example where the test file was created by snakemake --dag ::

        from sequana import sequana_data
        from sequana.snaketools import DOTParser

        filename = sequana_data("test_dag.dot")
        dot = DOTParser(filename)

        # creates test_dag.ann.dot locally
        dot.add_urls("test.dot", {"fastqc": "fastqc.html"})

    You can then convert the dag in an unix shell::

        dot -Tsvg test.ann.dot -o test.svg

    .. plot::

        from sequana import sequana_data
        from sequana.snaketools import DOTParser
        dot = DOTParser(sequana_data("test_dag.dot"))
        dot.add_urls("test.dot", {"fastqc": "fastqc.html"})
        from easydev import execute
        execute("dot -Tpng test.ann.dot -o test.png")
        from pylab import imshow, imread, xticks, yticks
        imshow(imread("test.png")); xticks([]) ;yticks([])

    """

    _name_to_drops = {"dag", "conda", "rulegraph", "copy_multiple_files"}

    def __init__(self, filename):
        """.. rubric:: constructor

        :param str filename: a DAG in dot format created by snakemake

        """
        self.filename = filename
        self.re_index = re.compile(r"(\d+)\[")
        self.re_name = re.compile(r'label = "(\w+)"')
        self.re_arrow = re.compile(r"(\d+) -> (\d+)")

    def add_urls(self, output_filename=None, mapper={}, title=None):
        # Open the original file
        with open(self.filename, "r") as fh:
            data = fh.read()

        if not output_filename:
            output_filename = os.path.basename(self.filename).replace(".dot", ".ann.dot")

        # The DOT parsing
        with open(output_filename, "w") as fout:
            indices_to_drop = set()
            for line in data.split("\n"):
                if line.strip().startswith("node["):
                    fout.write(
                        ' node[style="filled"; shape=box, color="black", fillcolor="#FCF3CF",'
                        " fontname=sans, fontsize=10, penwidth=2];\n"
                    )
                    continue
                if line.strip().startswith("edge["):
                    fout.write(" edge[penwidth=2, color=black]; \n")
                    continue

                if line.strip() == "}":
                    if title:
                        fout.write('overlap=false\nlabel="%s"\nfontsize=10;\n}\n' % title)
                    else:
                        fout.write(line)
                    continue

                name = self.re_name.search(line)
                if name:
                    name = name.group(1)
                    if name in self._name_to_drops:
                        index = self.re_index.search(line).group(1)
                        indices_to_drop.add(index)
                    elif name in mapper.keys():
                        url = mapper[name]
                        newline = line.split(name)[0] + name + '"'
                        newline += (' URL="%s", target="_parent", fillcolor="#5499C7"' "];\n") % url
                        # newline = line.replace('];', newline)
                        newline = newline.replace("dashed", "")
                        fout.write(newline)
                    else:
                        newline = line.split(name)[0] + name + '"];\n'
                        fout.write(newline)
                else:
                    arrow = self.re_arrow.findall(line)
                    if arrow:
                        index = arrow[0]
                        if not self._drop_arrow(index, indices_to_drop):
                            fout.write(line + "\n")
                    else:
                        line = line.replace("dashed", "")
                        fout.write(line + "\n")

    def _drop_arrow(self, index, indices_to_drop, title=None):
        for i in index:
            if i in indices_to_drop:
                return True
        return False
