# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import inspect

from types import FrameType
from typing import Iterable, Any

from .defines import CALLGUARD_ENABLED, CALLGUARD_STRICT_SELF, CALLGUARD_SELF_IS_FIRST_ARGUMENT, LOG


# MARK: Frame inspection utilities
def get_execution_frame(*, frames_up : int = 0) -> FrameType:
    # WARNING: It is important to 'del frame' once you are done with the frame!

    if frames_up < 0:
        raise ValueError("frames_up must be non-negative")

    n_frames = frames_up

    frame = inspect.currentframe()
    if frame is None:
        raise RuntimeError("No current frame available")

    try:
        while True:
            # Get the next frame up the stack
            next_frame = frame.f_back
            if next_frame is None:
                raise RuntimeError("No caller frame available")
            n_frames -= 1

            del frame
            frame = next_frame
            if n_frames <= 0:
                return frame
    except:
        del frame
        raise

def get_execution_frame_module(frame : FrameType) -> str | None:
    return frame.f_globals.get("__name__", None)

def get_execution_frame_self_varname(frame : FrameType) -> str | Iterable[str] | None:
    if not CALLGUARD_SELF_IS_FIRST_ARGUMENT:
        return ('self', 'cls')

    # Get the name of the first argument of the function/method in this frame
    code = frame.f_code
    if code.co_argcount <= 0:
        return None
    result = code.co_varnames[0]
    if CALLGUARD_STRICT_SELF:
        if result not in ('self', 'cls'):
            return None

    return result

def get_execution_frame_self(frame : FrameType) -> object | None:
    self_varnames = get_execution_frame_self_varname(frame)
    if self_varnames is None:
        return None
    if isinstance(self_varnames, str):
        self_varnames = (self_varnames,)

    for self_varname in self_varnames:
        result = frame.f_locals.get(self_varname, None)
        if result is not None:
            return result
    return None

def callguard_enabled(obj : Any = None, skip_if_already_guarded : bool = True) -> bool:
    result = CALLGUARD_ENABLED and not getattr(obj, '__callguard_disabled__', False) and (not getattr(obj, '__callguarded__', False) or not skip_if_already_guarded)
    if not result:
        LOG.debug(f"Callguard: Object {obj.__name__} is not callguard-enabled, skipping")
    return result