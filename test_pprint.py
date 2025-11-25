import re

import rich.pretty

from frozendict import frozendict


foo = frozendict(
    {
        re.compile(r"^test1$"): "value1",
    }
)

bar = {"foo": foo}

rich.pretty.pprint(bar, indent_guides=True, expand_all=True)
