# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import datetime

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

from sphinx_pyproject import SphinxConfig as PyProjectSphinxConfig
config = PyProjectSphinxConfig("../pyproject.toml")

project = config.name
author = config.author
copyright = f"{datetime.datetime.now().year} {author}"
release = config.version


# We need to import modules from one directory up
import os
import sys
sys.path.insert(0, os.path.abspath('..'))


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon', # For Google-style docstrings
    'sphinx_autodoc_typehints', # For type hints in docstrings
    'sphinx.ext.inheritance_diagram', # For class inheritance diagrams
    'sphinx.ext.intersphinx', # For linking to other projects' documentation
    'sphinx.ext.githubpages', # For GitHub Pages support
    'myst_parser', # For parsing Markdown files
]

autosummary_generate = True  # Turn on sphinx.ext.autosummary
autosummary_ignore_imports = True

autoclass_content = 'class'

autodoc_warningiserror = True  # Treat warnings as errors in autodoc
autodoc_class_signature = 'separated'  # Use the 'separated' style for class signatures
autodoc_inherit_docstrings = False  # Do not inherit docstrings from parent classes
autodoc_typehints = 'both'  # Show type hints in both the signature and the docstring

inheritance_graph_attrs = dict(size='""')

templates_path = ['_templates']
exclude_patterns = []

myst_heading_anchors = 5

myst_enable_extensions = [
    "colon_fence",
    "linkify",
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3.13', None),
    'rich': ('https://rich.readthedocs.io/en/latest/', None),
    'pydantic': ('https://docs.pydantic.dev/latest/', None),
    'requests': ('https://docs.python-requests.org/en/latest/', None),
    'requests_cache': ('https://requests-cache.readthedocs.io/en/stable/', None),
    'requests_ratelimiter': ('https://requests-ratelimiter.readthedocs.io/en/stable/', None),
}

source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']

html_theme_options = {
    'navigation_depth': -1,
    'sticky_navigation': True,
    'titles_only': True,
    'style_external_links': True,
}




# -- Custom Sphinx extension for converting Markdown links to RST format ------
import re
from sphinx.application import Sphinx

# Matches [`Text`][fully.qualified.name]
MD_REF = re.compile(r"\[`([^\]]+)`\]\[([^\]]+)\]")
# Matches [`fully.qualified.name`] (only if it looks dotted)
MD_FQNAME = re.compile(r"\[`([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)`\]")

def md_links_to_rst(app, what, name, obj, options, lines):
    for i, line in enumerate(lines):
        # Convert [`Text`][target] → :py:obj:`Text <target>`
        line = MD_REF.sub(r":py:obj:`\1 <\2>`", line)
        # Convert [`fully.qualified.name`] → :py:obj:`fully.qualified.name`
        line = MD_FQNAME.sub(r":py:obj:`\1`", line)
        lines[i] = line

import typing
def setup(app: Sphinx):
    app.connect("autodoc-process-docstring", md_links_to_rst)