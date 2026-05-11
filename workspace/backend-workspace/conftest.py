# Root conftest.py — blocks broken third-party pytest plugins
# The web3 pytest_ethereum plugin has a broken import in this environment
# (eth_typing.ContractName missing). Unregister it before it causes a crash.

collect_ignore_glob = []


def pytest_configure(config):
    try:
        config.pluginmanager.unregister(name="pytest_ethereum")
    except Exception:
        pass
