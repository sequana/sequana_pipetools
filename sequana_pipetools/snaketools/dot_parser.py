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
import subprocess
import tempfile

import rich_click as click


class DOTParser:
    """Utility to manipulate the dot file returned by Snakemake

    This class is used in the *dag* and *rulegraph* rules used in the
    snakemake pipeline. The input must be a dag/rulegraph created by snakemake.

    Consider this example where the test file was created by snakemake --dag ::

        from sequana_pipetools.snaketools import DOTParser

        dot = DOTParser("test_dag.dot")

        # creates test.dot locally with URLs added on the fastqc node
        dot.add_urls("test.dot", {"fastqc": "fastqc.html"})

    You can then convert the dag in an unix shell::

        dot -Tsvg test.ann.dot -o test.svg

    Even simpler, given your dot file, you can use the sequana_pipetools standalone
    as follows::

        sequana_pipetools --dot2png input.dot

    or read the dot file from the standard input (use - as the input name)::

        snakemake --rulegraph | sequana_pipetools --dot2png - -o rulegraph.png

    """

    _name_to_drops = {"dag", "rulegraph", "copy_multiple_files"}

    def __init__(self, filename=None, content=None):
        """.. rubric:: constructor

        :param str filename: a DAG in dot format created by snakemake
        :param str content: the DAG itself (dot format) as a string. Useful to
            read the output of e.g. **snakemake --rulegraph** from a pipe. Either
            *filename* or *content* must be provided.

        """
        if filename is None and content is None:
            raise ValueError("You must provide either a filename or a content (dot format)")
        self.filename = filename
        self.content = content
        self.re_index = re.compile(r"(\d+)\[")
        self.re_name = re.compile(r'label = "([\w\n\s,.!?-_:]+)"')
        self.re_arrow = re.compile(r"(\d+) -> (\d+)")

    def add_urls(self, output_filename=None, mapper={}, title=None):
        """Annotate the DAG and save it. Returns the name of the file created."""
        # Read the original DAG (from a file or from the content provided)
        if self.content is not None:
            data = self.content
        else:
            with open(self.filename, "r") as fh:
                data = fh.read()

        if not output_filename:
            if self.filename is None:
                output_filename = "rulegraph.ann.dot"
            else:
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

        return output_filename

    def _drop_arrow(self, index, indices_to_drop, title=None):
        for i in index:
            if i in indices_to_drop:
                return True
        return False


def convert_dot_to_png(name, output=None, content=None):
    """Convert a Snakemake DAG/rulegraph DOT input into a PNG file."""
    if content is not None:
        if not content.strip():
            raise ValueError("No data found on the standard input.")
        d = DOTParser(content=content)
        outname = output or "rulegraph.sequana.png"
    else:
        if not name.endswith(".dot"):
            raise ValueError(f"Input file must have a .dot extension, got: {name}")
        d = DOTParser(name)
        outname = output or name.replace(".dot", ".sequana.png")

    with tempfile.NamedTemporaryFile(mode="w") as fout:
        d.add_urls(fout.name)
        try:
            status = subprocess.call(["dot", "-Tpng", fout.name, "-o", outname])
        except FileNotFoundError:
            raise click.ClickException("The 'dot' executable was not found. Please install graphviz.")
    if status != 0:
        raise click.ClickException(f"dot failed to convert your input into {outname} (error {status})")
    return outname
