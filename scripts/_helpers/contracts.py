import json
from dataclasses import dataclass
from hashlib import sha3_256

from ape import project
from ape.contracts.base import ContractContainer, ContractType
from hexbytes import HexBytes
from rich import print
from rich.markup import escape

from .basetypes import ContractConfig, DeploymentContext
from .transactions import check_different, check_owner, execute, execute_read

ZERO_ADDRESS = "0x" + "00" * 20


class GenericContract(ContractConfig):
    _address: str

    def __init__(self, *, key: str, address: str, version: str | None = None, abi_key: str):
        super().__init__(key, None, None, version=version, abi_key=abi_key)
        self._address = address

    def address(self):
        return self._address

    def deployable(self, contract: DeploymentContext) -> bool:  # noqa: PLR6301, ARG002
        return False

    def __repr__(self):
        return f"GenericContract[key={self.key}, address={self._address}]"


@dataclass
class ERC721(ContractConfig):
    def __init__(self, *, key: str, abi_key: str, address: str | None = None):
        super().__init__(key, None, project.ERC721, abi_key=abi_key, nft=True)
        if address:
            self.load_contract(address)


# TODO add whitelisting as config?
@dataclass
class P2PLendingControl(ContractConfig):
    def __init__(
        self, *, key: str, version: str | None = None, abi_key: str, trait_roots_key: str, address: str | None = None
    ):
        super().__init__(
            key,
            None,
            project.P2PLendingControl,
            version=version,
            abi_key=abi_key,
            deployment_deps=set(),
            deployment_args=[],
            config_deps={trait_roots_key: self.set_trait_roots},
        )
        self.trait_roots_key = trait_roots_key
        if address:
            self.load_contract(address)

    @check_owner
    def set_trait_roots(self, context: DeploymentContext):
        trait_roots = context[self.trait_roots_key]
        roots_to_update = [
            (self.get_collection_hash(collection), "0x" + root)
            for collection, root in trait_roots.items()
            if context.dryrun or self.root_needs_update(context, collection, root)
        ]
        if roots_to_update:
            execute(context, self.key, "change_collections_trait_roots", roots_to_update)
        else:
            print(f"Contract [blue]{escape(self.key)}[/] change_collections_trait_roots with no roots, skipping update")

    def root_needs_update(self, context: DeploymentContext, collection: str, root: str) -> bool:
        collection_hash = self.get_collection_hash(collection)
        current_root = execute_read(context, self.key, "trait_roots", collection_hash)
        # print(f"Current root for {collection} is {current_root.hex()}, new is {root}")
        if current_root.hex() == "0x" + root:
            print(f"Contract [blue]{escape(self.key)}[/] trait root for {collection} is already {root}, skipping update")
            return False
        return True

    @staticmethod
    def get_collection_hash(collection: str) -> str:
        return "0x" + sha3_256(collection.encode()).hexdigest()


@dataclass
class P2PLendingNfts(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        payment_token_key: str,
        delegation_registry_key: str,
        cryptopunks_key: str,
        address: str | None = None,
        protocol_upfront_fee: int,
        protocol_settlement_fee: int,
        protocol_wallet: str,
        p2p_controller_key: str,
        max_protocol_upfront_fee: int,
        max_protocol_settlement_fee: int,
        max_lender_broker_settlement_fee: int,
        max_borrower_broker_settlement_fee: int,
    ):
        super().__init__(
            key,
            None,
            project.P2PLendingNfts,
            version=version,
            abi_key=abi_key,
            deployment_deps={payment_token_key, delegation_registry_key, cryptopunks_key, p2p_controller_key},
            deployment_args=[
                payment_token_key,
                p2p_controller_key,
                delegation_registry_key,
                cryptopunks_key,
                protocol_upfront_fee,
                protocol_settlement_fee,
                protocol_wallet,
                max_protocol_upfront_fee,
                max_protocol_settlement_fee,
                max_lender_broker_settlement_fee,
                max_borrower_broker_settlement_fee,
            ],
        )
        if address:
            self.load_contract(address)


@dataclass
class CryptoPunks(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.CryptoPunksMarketMock,
            version=version,
            abi_key=abi_key,
            nft=True,
        )
        if address:
            self.load_contract(address)


@dataclass
class ERC20(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        name: str,
        symbol: str,
        decimals: int,
        supply: str,
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.WETH9Mock,
            version=version,
            abi_key=abi_key,
            deployment_args=[name, symbol, decimals, int(supply)],
        )
        if address:
            self.load_contract(address)


@dataclass
class DelegationRegistry(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        address: str | None = None,
    ):
        container = DelegateRegistry2Container()
        super().__init__(
            key,
            None,
            container,
            version=version,
            abi_key=abi_key,
            deployment_deps=[],
            deployment_args=[],
        )
        if address:
            self.load_contract(address)


class DelegateRegistry2Container(ContractContainer):
    def __init__(self):
        with open("contracts/auxiliary/DelegateRegistry2_abi.json", "r") as f:
            abi = json.load(f)
        with open("contracts/auxiliary/DelegateRegistry2_deployment.hex", "r") as f:
            deployment_bytecode = HexBytes(f.read().strip())
        with open("contracts/auxiliary/DelegateRegistry2_runtime.hex", "r") as f:
            runtime_bytecode = HexBytes(f.read().strip())
        contract = ContractType(
            contractName="DelegateRegistry2",
            abi=abi,
            deploymentBytecode=deployment_bytecode,
            runtimeBytecode=runtime_bytecode,
        )
        super().__init__(contract)
