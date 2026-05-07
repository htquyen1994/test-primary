# Root conftest.py — blocks broken third-party pytest plugins
# The web3 pytest plugin in this environment has a broken import.
# This file prevents it from loading.

collect_ignore_glob = []
