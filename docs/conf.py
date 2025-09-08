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
autodoc_mock_imports = ['_typeshed']

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

def setup(app: Sphinx):
    app.connect("autodoc-process-docstring", md_links_to_rst)



# ---------- Custom sphinx extension to fix Python 3.14 annotations ------------
import functools, annotationlib, inspect

# sphinx.ext.autodoc
inspect_signature = inspect.signature
@functools.wraps(inspect.signature)
def patched_inspect_signature(*args, **kwargs):
    if 'annotation_format' not in kwargs:
        kwargs['annotation_format'] = annotationlib.Format.FORWARDREF
    return inspect_signature(*args, **kwargs)
inspect.signature = patched_inspect_signature

# sphinx_autodoc_typehints
import sphinx_autodoc_typehints
from typing import Callable, TypeVar, Any

sphinx_autodoc_typehints_process_signature = sphinx_autodoc_typehints.process_signature
@functools.wraps(sphinx_autodoc_typehints_process_signature)
def patched_sphinx_autodoc_typehints_process_signature(app, what, name, obj, options, signature, return_annotation: str):
    if not callable(obj):
        return None

    original_obj = obj
    obj = getattr(obj, "__init__", getattr(obj, "__new__", None)) if inspect.isclass(obj) else obj
    annotations = annotationlib.get_annotations(obj, format=annotationlib.Format.FORWARDREF)
    if not annotations:  # when has no annotation we cannot autodoc typehints so bail
        return None

    obj = inspect.unwrap(obj)
    sph_signature = sphinx_autodoc_typehints.sphinx_signature(obj, type_aliases=app.config["autodoc_type_aliases"])
    typehints_formatter: Callable[..., str | None] | None = getattr(app.config, "typehints_formatter", None)

    def _get_formatted_annotation(annotation: TypeVar) -> TypeVar:
        if typehints_formatter is None:
            return annotation
        formatted_name = typehints_formatter(annotation)
        return annotation if not isinstance(formatted_name, str) else TypeVar(formatted_name)

    if app.config.typehints_use_signature_return:
        sph_signature = sph_signature.replace(
            return_annotation=_get_formatted_annotation(sph_signature.return_annotation)
        )

    if app.config.typehints_use_signature:
        parameters = [
            param.replace(annotation=_get_formatted_annotation(param.annotation))
            for param in sph_signature.parameters.values()
        ]
    else:
        parameters = [param.replace(annotation=inspect.Parameter.empty) for param in sph_signature.parameters.values()]

    # if we have parameters we may need to delete first argument that's not documented, e.g. self
    start = 0
    if parameters:
        if inspect.isclass(original_obj) or (what == "method" and name.endswith(".__init__")):
            start = 1
        elif what == "method":
            # bail if it is a local method as we cannot determine if first argument needs to be deleted or not
            if "<locals>" in obj.__qualname__ and not sphinx_autodoc_typehints._is_dataclass(name, what, obj.__qualname__):
                sphinx_autodoc_typehints._LOGGER.warning('Cannot handle as a local function: "%s" (use @functools.wraps)', name)
                return None
            outer = inspect.getmodule(obj)
            for class_name in obj.__qualname__.split(".")[:-1]:
                outer = getattr(outer, class_name)
            method_name = obj.__name__
            if method_name.startswith("__") and not method_name.endswith("__"):
                # when method starts with double underscore Python applies mangling -> prepend the class name
                method_name = f"_{obj.__qualname__.split('.')[-2]}{method_name}"
            method_object = outer.__dict__[method_name] if outer else obj
            if not isinstance(method_object, classmethod | staticmethod):
                start = 1

    sph_signature = sph_signature.replace(parameters=parameters[start:])
    show_return_annotation = app.config.typehints_use_signature_return
    unqualified_typehints = not getattr(app.config, "typehints_fully_qualified", False)
    return (
        sphinx_autodoc_typehints.stringify_signature(
            sph_signature,
            show_return_annotation=show_return_annotation,
            unqualified_typehints=unqualified_typehints,
        ).replace("\\", "\\\\"),
        None,
    )
sphinx_autodoc_typehints.process_signature = patched_sphinx_autodoc_typehints_process_signature

sphinx_autodoc_typehints_get_type_hint = sphinx_autodoc_typehints._get_type_hint
@functools.wraps(sphinx_autodoc_typehints_get_type_hint)
def patched_sphinx_autodoc_typehints_get_type_hint(autodoc_mock_imports, name, obj, localns):
    sphinx_autodoc_typehints._resolve_type_guarded_imports(autodoc_mock_imports, obj)
    try:
        result = sphinx_autodoc_typehints.get_type_hints(obj, None, localns)
    except (AttributeError, TypeError, RecursionError) as exc:
        # TypeError - slot wrapper, PEP-563 when part of new syntax not supported
        # RecursionError - some recursive type definitions https://github.com/python/typing/issues/574
        if isinstance(exc, TypeError) and sphinx_autodoc_typehints._future_annotations_imported(obj) and "unsupported operand type" in str(exc):
            result = annotationlib.get_annotations(obj, format=annotationlib.Format.FORWARDREF)
        else:
            result = {}
    except NameError as exc:
        #sphinx_autodoc_typehints._LOGGER.warning('Cannot resolve forward reference in type annotations of "%s": %s', name, exc)
        result = annotationlib.get_annotations(obj, format=annotationlib.Format.STRING)
    return result
sphinx_autodoc_typehints._get_type_hint = patched_sphinx_autodoc_typehints_get_type_hint