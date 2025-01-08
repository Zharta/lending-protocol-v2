import os
from datetime import datetime as dt
from hashlib import sha3_256
from textwrap import dedent

import boa
import pytest
from boa.environment import Env
from boa.vm.py_evm import register_raw_precompile
from eth_account import Account
from web3 import Web3

from ..conftest_base import ZERO_ADDRESS, get_last_event


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: mark test as slow to run")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)


@pytest.fixture(scope="session", autouse=True)
def boa_env():
    old_env = boa.env
    new_env = Env()
    new_env._cached_call_profiles = old_env._cached_call_profiles
    new_env._cached_line_profiles = old_env._cached_line_profiles
    new_env._profiled_contracts = old_env._profiled_contracts

    with boa.swap_env(new_env):
        fork_uri = os.environ["BOA_FORK_RPC_URL"]
        disable_cache = os.environ.get("BOA_FORK_NO_CACHE")
        kw = {"cache_file": None} if disable_cache else {}
        blkid = 21325933

        boa.env.fork(fork_uri, block_identifier=blkid, **kw)
        yield

        old_env._cached_call_profiles = new_env._cached_call_profiles
        old_env._cached_line_profiles = new_env._cached_line_profiles
        old_env._profiled_contracts = new_env._profiled_contracts


@pytest.fixture(scope="session")
def accounts(boa_env):
    _accounts = [boa.env.generate_address() for _ in range(10)]
    for account in _accounts:
        boa.env.set_balance(account, 10**21)
    return _accounts


@pytest.fixture(scope="session")
def owner_account():
    return Account.create()


@pytest.fixture(scope="session")
def owner(owner_account, boa_env):
    boa.env.eoa = owner_account.address
    boa.env.set_balance(owner_account.address, 10**21)
    return owner_account.address


@pytest.fixture(scope="session")
def owner_key(owner_account):
    return owner_account.key


@pytest.fixture(scope="session")
def borrower_account():
    return Account.create()


@pytest.fixture(scope="session")
def borrower(borrower_account, boa_env):
    boa.env.set_balance(borrower_account.address, 10**21)
    return borrower_account.address


@pytest.fixture(scope="session")
def borrower_key(borrower_account):
    return borrower_account.key


@pytest.fixture(scope="session")
def lender_account():
    return Account.create()


@pytest.fixture(scope="session")
def lender(lender_account, boa_env):
    boa.env.set_balance(lender_account.address, 10**21)
    return lender_account.address


@pytest.fixture(scope="session")
def lender_key(lender_account):
    return lender_account.key


@pytest.fixture(scope="session")
def lender2_account():
    return Account.create()


@pytest.fixture(scope="session")
def lender2(lender2_account, boa_env):
    boa.env.set_balance(lender2_account.address, 10**21)
    return lender2_account.address


@pytest.fixture(scope="session")
def lender2_key(lender2_account):
    return lender2_account.key


@pytest.fixture(scope="session")
def protocol_wallet(accounts):
    yield accounts[3]


@pytest.fixture(scope="session")
def erc721_contract_def(boa_env):
    return boa.load_partial("contracts/auxiliary/ERC721.vy")


@pytest.fixture(scope="session")
def weth9_contract_def(boa_env):
    # return boa.load_partial("contracts/auxiliary/WETH9Mock.vy")
    return boa.load_abi("contracts/auxiliary/WETH9_abi.json")


@pytest.fixture(scope="session")
def erc20_contract_def():
    return boa.load_abi("contracts/auxiliary/USDC_abi.json")


@pytest.fixture(scope="session")
def cryptopunks_market_contract_def():
    return boa.load_partial("tests/stubs/CryptoPunksMarketStub.vy")


@pytest.fixture(scope="session")
def weth(weth9_contract_def, owner, accounts):
    weth = weth9_contract_def.at("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
    holder = "0xF04a5cC80B1E94C69B48f5ee68a08CD2F09A7c3E"
    with boa.env.prank(holder):
        for account in accounts:
            weth.transfer(account, 10**21, sender=holder)
    weth.transfer(owner, 10**21, sender=holder)
    return weth


@pytest.fixture(scope="module")
def usdc(owner, accounts, erc20_contract_def):
    erc20 = erc20_contract_def.at("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
    holder = "0x99C9fc46f92E8a1c0deC1b1747d010903E884bE1"
    with boa.env.prank(holder):
        for account in accounts:
            erc20.transfer(account, 10**12, sender=holder)
    erc20.transfer(owner, 10**12, sender=holder)
    return erc20


@pytest.fixture(scope="session")
def cryptopunks_contract_def(boa_env):
    return boa.load_partial("contracts/auxiliary/CryptoPunksMarketMock.vy")


@pytest.fixture(scope="session")
def cryptopunks(cryptopunks_contract_def, owner):
    return cryptopunks_contract_def.deploy()


@pytest.fixture(scope="session")
def delegation_registry_contract_def(boa_env):
    return boa.load_partial("contracts/auxiliary/DelegationRegistryMock.vy")


@pytest.fixture(scope="session")
def p2p_lending_nfts_contract_def(boa_env):
    return boa.load_partial("contracts/P2PLendingNfts.vy")


@pytest.fixture(scope="session")
def p2p_lending_control_contract_def(boa_env):
    return boa.load_partial("contracts/P2PLendingControl.vy")


@pytest.fixture(scope="session")
def p2p_lending_nfts_proxy_contract_def(boa_env):
    return boa.load_partial("tests/stubs/P2PNftsProxy.vy")


@pytest.fixture(scope="module")
def punks(owner, cryptopunks_market_contract_def):
    return cryptopunks_market_contract_def.at("0xb47e3cd837dDF8e4c57F05d70Ab865de6e193BBB")


@pytest.fixture
def punks_key_hash():
    return sha3_256(b"cryptopunks").digest()


@pytest.fixture(scope="module")
def bayc(owner, erc721_contract_def):
    return erc721_contract_def.at("0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D")


@pytest.fixture
def bayc_key_hash():
    return sha3_256(b"bayc").digest()


@pytest.fixture
def mayc(owner, erc721_contract_def):
    return erc721_contract_def.at("0x60E4d786628Fea6478F785A6d7e704777c86a7c6")


@pytest.fixture
def mayc_key_hash():
    return sha3_256(b"mayc").digest()


@pytest.fixture
def wpunk(owner, erc721_contract_def):
    return boa.load_abi("contracts/auxiliary/wpunk_abi.json").at("0xb7F7F6C52F2e2fdb1963Eab30438024864c313F6")
    # return erc721_contract_def.at("0xb7F7F6C52F2e2fdb1963Eab30438024864c313F6")


@pytest.fixture
def wpunk_key_hash():
    return sha3_256(b"wpunk").digest()


@pytest.fixture(scope="module")
def koda(owner, erc721_contract_def):
    return erc721_contract_def.at("0xE012Baf811CF9c05c408e879C399960D1f305903")


@pytest.fixture
def koda_key_hash():
    return sha3_256(b"othersidekoda").digest()


@pytest.fixture
def captainz(owner, erc721_contract_def):
    return erc721_contract_def.at("0x769272677faB02575E84945F03Eca517ACc544Cc")


@pytest.fixture
def captainz_key_hash():
    return sha3_256(b"thecaptainz").digest()


@pytest.fixture(scope="module")
def otherdeed_for_otherside_contract(owner, erc721_contract_def):
    return erc721_contract_def.at("0x34d85c9CDeB23FA97cb08333b511ac86E1C4E258")


@pytest.fixture(scope="module")
def delegation_registry(owner, delegation_registry_contract_def):
    return delegation_registry_contract_def.at("0x00000000000076A84feF008CDAbe6409d2FE638B")


@pytest.fixture
def balancer(boa_env):
    return boa.load_abi("contracts/auxiliary/BalancerFlashLoanProvider.json", name="Balancer").at(
        "0x4EAF187ad4cE325bF6C84070b51c2f7224A51321"
    )


@pytest.fixture(scope="module")
def empty_contract_def(boa_env):
    return boa.loads_partial(
        dedent(
            """
        dummy: uint256
     """
        )
    )


@boa.precompile("def debug_bytes(data: Bytes[1024])")
def debug_bytes(data: bytes):
    print(f"DEBUG: {data.hex()} {data.decode()}")


@pytest.fixture(scope="session")
def debug_precompile(boa_env):
    register_raw_precompile("0x0000000000000000000000000000000000011111", debug_bytes)
    yield


@pytest.fixture(scope="session")
def gondi_proxy_contract_def():
    return boa.load_partial("contracts/GondiProxy.vy")


@pytest.fixture(scope="session")
def nftfi_proxy_contract_def():
    return boa.load_partial("contracts/NftfiProxy.vy")


@pytest.fixture(scope="session")
def arcade_proxy_contract_def():
    return boa.load_partial("contracts/ArcadeProxy.vy")


@pytest.fixture(scope="session")
def x2y2_proxy_contract_def():
    return boa.load_partial("contracts/X2Y2Proxy.vy")


@pytest.fixture(scope="session")
def benddao_proxy_contract_def():
    return boa.load_partial("contracts/BendDAOProxy.vy")


@pytest.fixture
def now():
    return boa.eval("block.timestamp")
