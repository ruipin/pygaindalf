# SPDX-License-Identifier: GPLv3
# Copyright © 2025 pygaindalf Rui Pinheiro

import logging
import os
import tempfile
import pytest

from app.util.logging import getLogger

@pytest.mark.logging
class TestLogger:
    def test_getLogger_returns_logger(self, caplog):
        logger = getLogger('testLogger')
        with caplog.at_level(logging.INFO):
            logger.debug('debug message')
            logger.info('info message')
            logger.warning('warning message')
            logger.error('error message')
        assert 'debug message' not in caplog.text
        assert 'info message' in caplog.text
        assert 'warning message' in caplog.text
        assert 'error message' in caplog.text

    def test_getLogger_with_parent(self, caplog):
        parent = getLogger('parentLogger')
        child = getLogger('childLogger', parent=parent)
        assert child.parent is parent
        assert child.name == 'parentLogger.childLogger'
        with caplog.at_level(logging.INFO):
            child.info('child info')
        assert 'child info' in caplog.text

    def test_logger_isEnabledFor(self):
        logger = getLogger('enabledLogger')
        assert logger.isEnabledFor(logging.INFO)
        assert not logger.isEnabledFor(logging.NOTSET)
        assert logger.isEnabledForTty(logging.INFO)
        assert not logger.isEnabledForFile(logging.INFO)

    def test_logger_invalid_handler(self):
        logger = getLogger('invalidHandlerLogger')
        with pytest.raises(ValueError):
            logger.isEnabledFor(logging.INFO, handler='invalid')
