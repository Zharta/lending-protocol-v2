# ruff: noqa: ERA001 PYI024

import contextlib
from collections import namedtuple
from dataclasses import dataclass, field
from enum import IntEnum
from functools import cached_property
from itertools import starmap
from textwrap import dedent
from typing import NamedTuple

import boa
import eth_abi
import vyper
from boa.contracts.vyper.event import Event
from boa.contracts.vyper.vyper_contract import VyperContract
from eth.exceptions import Revert
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_intended_validator, encode_structured_data
from eth_utils import encode_hex, keccak
from web3 import Web3

ZERO_ADDRESS = boa.eval("empty(address)")
ZERO_BYTES32 = boa.eval("empty(bytes32)")


def get_last_event(contract: VyperContract, name: str | None = None):
    # print("CONTRACT LOGS", contract.get_logs())
    # print("\n\n\n")
    matching_events = [e for e in contract.get_logs() if isinstance(e, Event) and (name is None or name == e.event_type.name)]
    return EventWrapper(matching_events[-1])


def get_events(contract: VyperContract, name: str | None = None):
    return [
        EventWrapper(e) for e in contract.get_logs() if isinstance(e, Event) and (name is None or name == e.event_type.name)
    ]


class EventWrapper:
    def __init__(self, event: Event):
        self.event = event
        self.event_name = event.event_type.name

    def __getattr__(self, name):
        print(f"getattr {self=} {name=}")
        if name in self.args_dict:
            return self.args_dict[name]
        raise AttributeError(f"No attr {name} in {self.event_name}. Event data is {self.event}")

    @cached_property
    def args_dict(self):
        # print(f"{self.event=} {self.event.event_type.arguments=}")
        args = self.event.event_type.arguments.keys()
        indexed = self.event.event_type.indexed
        topic_values = (v for v in self.event.topics)
        args_values = (v for v in self.event.args)
        _args = [(arg, next(topic_values) if indexed[i] else next(args_values)) for i, arg in enumerate(args)]

        return {k: self._format_value(v, self.event.event_type.arguments[k]) for k, v in _args}

    def _format_value(self, v, _type):  # noqa: PLR6301
        # print(f"_format_value {v=} {_type=} {type(v).__name__=} {type(_type)=}")
        if isinstance(_type, vyper.semantics.types.primitives.AddressT):
            return Web3.to_checksum_address(v)
        if isinstance(_type, vyper.semantics.types.primitives.BytesT):
            return f"0x{v.hex()}"
        return v

    def __repr__(self):
        return f"<EventWrapper {self.event_name} {self.args_dict}>"


@contextlib.contextmanager
def deploy_reverts():
    try:
        yield
        raise ValueError("Did not revert")
    except Revert:
        ...


Offer = namedtuple(
    "Offer",
    [
        "principal",
        "interest",
        "payment_token",
        "duration",
        "origination_fee_amount",
        "broker_upfront_fee_amount",
        "broker_settlement_fee_bps",
        "broker_address",
        "collateral_contract",
        "collateral_min_token_id",
        "collateral_max_token_id",
        "expiration",
        "lender",
        "pro_rata",
        "size",
    ],
    defaults=[0, 0, ZERO_ADDRESS, 0, 0, 0, 0, ZERO_ADDRESS, ZERO_ADDRESS, 0, 0, 0, ZERO_ADDRESS, False, 0],
)


class FeeType(IntEnum):
    PROTOCOL = 1 << 0
    ORIGINATION = 1 << 1
    LENDER_BROKER = 1 << 2
    BORROWER_BROKER = 1 << 3


Signature = namedtuple("Signature", ["v", "r", "s"], defaults=[0, ZERO_BYTES32, ZERO_BYTES32])


SignedOffer = namedtuple("SignedOffer", ["offer", "signature"], defaults=[Offer(), Signature()])


class Fee(NamedTuple):
    type: FeeType = FeeType.PROTOCOL
    upfront_amount: int = 0
    settlement_bps: int = 0
    wallet: str = ZERO_ADDRESS

    @classmethod
    def protocol(cls, contract):
        return cls(
            FeeType.PROTOCOL, contract.protocol_upfront_fee(), contract.protocol_settlement_fee(), contract.protocol_wallet()
        )

    @classmethod
    def origination(cls, offer):
        return cls(FeeType.ORIGINATION, offer.origination_fee_amount, 0, offer.lender)

    @classmethod
    def lender_broker(cls, offer):
        return cls(
            FeeType.LENDER_BROKER, offer.broker_upfront_fee_amount, offer.broker_settlement_fee_bps, offer.broker_address
        )

    @classmethod
    def borrower_broker(cls, broker, upfront_amount=0, settlement_bps=0):
        return cls(FeeType.BORROWER_BROKER, upfront_amount, settlement_bps, broker)


FeeAmount = namedtuple("FeeAmount", ["type", "amount", "wallet"], defaults=[0, 0, ZERO_ADDRESS])


class Loan(NamedTuple):
    id: bytes = ZERO_BYTES32
    amount: int = 0
    interest: int = 0
    payment_token: str = ZERO_ADDRESS
    maturity: int = 0
    start_time: int = 0
    borrower: str = ZERO_ADDRESS
    lender: str = ZERO_ADDRESS
    collateral_contract: str = ZERO_ADDRESS
    collateral_token_id: int = 0
    fees: list[Fee] = field(default_factory=list)
    pro_rata: bool = False

    def get_protocol_fee(self):
        return next((f for f in self.fees if f.type == FeeType.PROTOCOL), None)

    def get_lender_broker_fee(self):
        return next((f for f in self.fees if f.type == FeeType.LENDER_BROKER), None)

    def get_borrower_broker_fee(self):
        return next((f for f in self.fees if f.type == FeeType.BORROWER_BROKER), None)

    def get_origination_fee(self):
        return next((f for f in self.fees if f.type == FeeType.ORIGINATION), None)

    def get_settlement_fees(self, timestamp=None):
        interest = self.get_interest(timestamp) if timestamp else self.interest
        return sum(f.settlement_bps * interest // 10000 for f in self.fees)

    def get_interest(self, timestamp):
        if self.pro_rata:
            return self.interest * (timestamp - self.start_time) // (self.maturity - self.start_time)
        return self.interest


BrokerLock = namedtuple("BrokerLock", ["broker", "expiration"], defaults=[ZERO_ADDRESS, 0])


class CollateralStatus(NamedTuple):
    broker_lock: BrokerLock = BrokerLock()
    whitelisted: bool = False

    @classmethod
    def from_tuple(cls, t):
        broker_lock, whitelisted = t
        return cls(BrokerLock(*broker_lock), whitelisted)


PunkOffer = namedtuple(
    "PunkOffer",
    ["isForSale", "punkIndex", "seller", "minValue", "onlySellTo"],
    defaults=[False, 0, ZERO_ADDRESS, 0, ZERO_ADDRESS],
)


WhitelistRecord = namedtuple("WhitelistRecord", ["collection", "whitelisted"], defaults=[ZERO_ADDRESS, False])


def compute_loan_hash(loan: Loan):
    print(f"compute_loan_hash {loan=}")
    encoded = eth_abi.encode(
        [
            "(bytes32,uint256,uint256,address,uint256,uint256,address,address,address,uint256,(uint256,uint256,uint256,address)[],bool)"
        ],
        [loan],
    )
    return boa.eval(f"""keccak256({encoded})""")


def compute_signed_offer_id(offer: SignedOffer):
    return boa.eval(
        dedent(
            f"""keccak256(
            concat(
                convert({offer.signature.v}, bytes32),
                convert({offer.signature.r}, bytes32),
                convert({offer.signature.s}, bytes32),
            ))"""
        )
    )


def sign_offer(offer: Offer, lender_key: str, verifying_contract: str) -> SignedOffer:
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Offer": [
                {"name": "principal", "type": "uint256"},
                {"name": "interest", "type": "uint256"},
                {"name": "payment_token", "type": "address"},
                {"name": "duration", "type": "uint256"},
                {"name": "origination_fee_amount", "type": "uint256"},
                {"name": "broker_upfront_fee_amount", "type": "uint256"},
                {"name": "broker_settlement_fee_bps", "type": "uint256"},
                {"name": "broker_address", "type": "address"},
                {"name": "collateral_contract", "type": "address"},
                {"name": "collateral_min_token_id", "type": "uint256"},
                {"name": "collateral_max_token_id", "type": "uint256"},
                {"name": "expiration", "type": "uint256"},
                {"name": "lender", "type": "address"},
                {"name": "pro_rata", "type": "bool"},
                {"name": "size", "type": "uint256"},
            ],
        },
        "primaryType": "Offer",
        "domain": {
            "name": "Zharta",
            "version": "1",
            "chainId": boa.eval("chain.id"),
            "verifyingContract": verifying_contract,
        },
        "message": offer._asdict(),
    }
    signable_msg = encode_structured_data(typed_data)
    signed_msg = Account.from_key(lender_key).sign_message(signable_msg)
    lender_signature = Signature(signed_msg.v, signed_msg.r, signed_msg.s)

    return SignedOffer(offer, lender_signature)


def replace_namedtuple_field(namedtuple, **kwargs):
    return namedtuple.__class__(**namedtuple._asdict() | kwargs)


def replace_list_element(lst, index, value):
    return lst[:index] + [value] + lst[index + 1 :]


def get_loan_mutations(loan):
    random_address = boa.env.generate_address("random")

    yield replace_namedtuple_field(loan, id=ZERO_BYTES32)
    yield replace_namedtuple_field(loan, amount=loan.amount + 1)
    yield replace_namedtuple_field(loan, interest=loan.interest + 1)
    yield replace_namedtuple_field(loan, payment_token=random_address)
    yield replace_namedtuple_field(loan, maturity=loan.maturity - 1)
    yield replace_namedtuple_field(loan, start_time=loan.start_time - 1)
    yield replace_namedtuple_field(loan, borrower=random_address)
    yield replace_namedtuple_field(loan, lender=random_address)
    yield replace_namedtuple_field(loan, collateral_contract=random_address)
    yield replace_namedtuple_field(loan, collateral_token_id=loan.collateral_token_id + 1)
    yield replace_namedtuple_field(loan, pro_rata=not loan.pro_rata)

    fees = loan.fees
    if len(fees) < 4:
        yield replace_namedtuple_field(loan, fees=[*fees, Fee(FeeType.PROTOCOL, 0, 0, random_address)])

    for i, fee in enumerate(fees):
        yield replace_namedtuple_field(loan, fees=fees[:i] + fees[i + 1 :])
        yield replace_namedtuple_field(
            loan,
            fees=replace_list_element(fees, i, replace_namedtuple_field(fee, type=next(t for t in FeeType if t != fee.type))),
        )
        yield replace_namedtuple_field(
            loan, fees=replace_list_element(fees, i, replace_namedtuple_field(fee, upfront_amount=fee.upfront_amount + 1))
        )
        yield replace_namedtuple_field(
            loan, fees=replace_list_element(fees, i, replace_namedtuple_field(fee, settlement_bps=fee.settlement_bps + 1))
        )
        yield replace_namedtuple_field(
            loan, fees=replace_list_element(fees, i, replace_namedtuple_field(fee, wallet=random_address))
        )
