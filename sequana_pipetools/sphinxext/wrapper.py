# coding: utf-8 -*-
"""sequana wrappers

Defines a docutils directive for inserting simple docstring extracting from 
a sequana wrappers Snakefile .

::

    .. sequana_wrapper: dag

The name must be a valid sequana wrappers

"""
import re
import requests
from docutils.nodes import Body, Element


from docutils import nodes
from docutils.parsers.rst import Directive

from sphinx.locale import _
from sphinx.util.docutils import SphinxDirective


def get_rule_doc(name):
    """Decode and return the docstring(s) of a sequana wrapper."""


    url ="https://raw.githubusercontent.com/sequana/sequana-wrappers/master/sequana-wrappers/"
    r = requests.get(f"{url}/{name}/example.smk")
    
    data = r.content.decode()
    # Try to identify the rule and therefore possible docstring
    # It may be a standard rule or a dynamic rule !
    # standard one
    rulename_tag = "rule %s" % name
    if rulename_tag in data:
        data = data.split(rulename_tag, 1)[1]
    else:
        return "no docstring found for %s " % name

    # Find first """ or ''' after the rule definition
    single = data.find("'''")
    double = data.find('"""')
    if single > 0 and double > 0:
        if single > double:
            quotes = '"""'
        else:
            quotes = "'''"
    elif single > 0:
        quotes = "'''"
    elif double > 0:
        quotes = '"""'
    else:
        return "no docstring found for %s " % name

    start = data.find(quotes)
    end = data[start + 3 :].find(quotes) + start + 3

    if end == -1 or end < start:
        return "no end of docstring found for %s " % name

    docstring = data[start + 3 : end]
    return docstring


class snakemake_base(Body, Element):
    def dont_traverse(self, *args, **kwargs):
        return []


class sequana_wrapper(snakemake_base):
    pass


def run(content, node_class, state, content_offset):
    node = node_class("")  # shall we add something here ?
    name = content[0]
    try:
        node.rule_docstring = get_rule_doc(name)
    except Exception:
        node.rule_docstring(f"Could not read or interpret documentation for {name}")
    state.nested_parse(content, content_offset, node)
    return [node]


class SnakemakeDirective(SphinxDirective):

    has_content = True

    def run(self):
        return run(self.content, sequana_wrapper, self.state, self.content_offset)


def setup(app):

    setup.app = app
    setup.config = app.config
    setup.confdir = app.confdir
    app.add_directive("sequana_wrapper", SnakemakeDirective)

    # Add visit/depart methods to HTML-Translator:
    def visit_perform(self, node):
        # Ideally, we should use sphinx but this is a simple temporary solution
        from docutils import core
        from docutils.writers.html4css1 import Writer

        w = Writer()
        try:
            res = core.publish_parts(node.rule_docstring, writer=w)["html_body"]
            self.body.append('<div class="sequana_wrapper">' + res + "</div>")
            node.children = []
        except Exception as err:
            print(err)
            self.body.append('<div class="sequana_wrapper"> no docstring </div>')

    def depart_perform(self, node):
        node.children = []

    def depart_ignore(self, node):
        node.children = []

    def visit_ignore(self, node):
        node.children = []


    app.add_node(
        sequana_wrapper,
        html=(visit_perform, depart_perform),
        latex=(visit_ignore, depart_ignore),
    )

    return {
        "version": "todo in sequana_pipetools.sphinext",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
