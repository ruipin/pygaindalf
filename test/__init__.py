# SPDX-License-Identifier: GPLv3-or-later
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
import warnings


# Quieten faker logging
logging.getLogger("faker").setLevel(logging.WARNING)

# Quieten warnings in libraries we do not control
warnings.filterwarnings("ignore", module="cattrs")
