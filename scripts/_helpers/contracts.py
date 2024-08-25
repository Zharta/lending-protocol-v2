import json
from dataclasses import dataclass

from ape import project
from ape.contracts.base import ContractContainer, ContractType
from hexbytes import HexBytes

from .basetypes import ContractConfig, DeploymentContext

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
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        cryptopunks_key: str,
        max_broker_lock_duration: int,
        address: str | None = None,
    ):
        super().__init__(
            key,
            None,
            project.P2PLendingControl,
            version=version,
            abi_key=abi_key,
            deployment_deps={cryptopunks_key},
            deployment_args=[cryptopunks_key, max_broker_lock_duration],
            # config_deps={collateral_vault_peripheral_key: self.set_cvperiph},
        )
        # self.collateral_vault_peripheral_key = collateral_vault_peripheral_key
        if address:
            self.load_contract(address)

    # @check_owner
    # @check_different(getter="collateralVaultPeripheralAddress", value_property="collateral_vault_peripheral_key")
    # def set_cvperiph(self, context: DeploymentContext):
    #     execute(context, self.key, "setCollateralVaultPeripheralAddress", self.collateral_vault_peripheral_key)


@dataclass
class P2PLendingNfts(ContractConfig):
    def __init__(
        self,
        *,
        key: str,
        version: str | None = None,
        abi_key: str,
        payment_token_key: str | None = None,
        max_protocol_fee: int,
        delegation_registry_key: str,
        weth_key: str,
        cryptopunks_key: str,
        controller_key: str,
        address: str | None = None,
    ):
        payment_token_deps = [payment_token_key] if payment_token_key else []
        super().__init__(
            key,
            None,
            project.P2PLendingNfts,
            version=version,
            abi_key=abi_key,
            deployment_deps={*payment_token_deps, delegation_registry_key, weth_key, cryptopunks_key, controller_key},
            deployment_args=[
                payment_token_key or ZERO_ADDRESS,
                max_protocol_fee,
                delegation_registry_key,
                weth_key,
                cryptopunks_key,
                controller_key,
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
        with open("contracts/auxiliary/DelegateRegistry2_abi.json", encoding="locale") as f:
            abi = json.load(f)
        with open("contracts/auxiliary/DelegateRegistry2_deployment.hex", encoding="locale") as f:
            deployment_bytecode = HexBytes(f.read().strip())
        with open("contracts/auxiliary/DelegateRegistry2_runtime.hex", encoding="locale") as f:
            runtime_bytecode = HexBytes(f.read().strip())
        contract = ContractType(
            contractName="DelegateRegistry2",
            abi=abi,
            deploymentBytecode=deployment_bytecode,
            runtimeBytecode=runtime_bytecode,
        )
        super().__init__(contract)
