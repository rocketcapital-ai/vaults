from decimal import Decimal
import random
from brownie import project

USDC_ADDR = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'
SECS_PER_WK = 7 * 24 * 60 * 60

op = project.load("OpenZeppelin//openzeppelin-contracts@4.8.0")

class Colours:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    ORANGE = '\033[33m'
    PURPLE = '\033[35m'
    YELLOW = '\033[93m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    WHITE = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    BG = '\033[90m'


class MAX_LIMIT_ID:
    DEPOSIT = 0
    MINT = 1
    WITHDRAW = 2
    REDEEM = 3


class REQUEST_TYPE:
    DEPOSIT = 0
    WITHDRAW = 1


class RequestRecord:
    def __init__(self, request_record_list=None):
        if request_record_list is None:
            request_record_list = [None] * 6
        self.vault = request_record_list[0]
        self.request_type = request_record_list[1]
        self.sender = request_record_list[2]
        self.receiver = request_record_list[3]
        self.timestamp = request_record_list[4]
        self.amount = request_record_list[5]

    def to_list(self) -> list:
        return [
            self.vault,
            self.request_type,
            self.sender,
            self.receiver,
            self.timestamp,
            self.amount
        ]


class ProcessedRecord:
    def __init__(self, processed_record_list=None):
        if processed_record_list is None:
            processed_record_list = [None] * 6
        self.vault = processed_record_list[0]
        self.request_type = processed_record_list[1]
        self.receiver = processed_record_list[2]
        self.timestamp = processed_record_list[3]
        self.amountIn = processed_record_list[4]
        self.amountOut = processed_record_list[5]
        self.feesPaid = processed_record_list[6]

    def to_list(self) -> list:
        return [
            self.vault,
            self.request_type,
            self.receiver,
            self.timestamp,
            self.amountIn,
            self.amountOut,
            self.feesPaid
        ]


def dec(num: int or float or str):
    return Decimal(num)


def verify(exp, act, msg=""):
    assert exp == act, "\nExpected: {}\nActual: {}\n Message: ".format(exp, act, msg)


def verify_gte(greater, smaller, msg=""):
    assert greater >= smaller, "\nGreater val: {}\nSmaller val: {}\n Message: ".format(greater, smaller, msg)


def verify_diff(greater, smaller, exp_diff=1, bidirectional=False, msg=""):
    diff = greater - smaller
    if bidirectional: diff = abs(diff)
    assert diff <= exp_diff, "\nGreater val: {}\nSmaller val: {}\nDifference: {}\n Message: ".format(greater,
                                                                                                     smaller,
                                                                                                     greater - smaller,
                                                                                                     msg)


def fr(sender):
    return {"from": sender}


def verify_event(expected: [tuple], actual: [tuple]):
    for exp, act in zip(expected, actual):
        verify(exp, act)


def calculate_fee(pct, amount):
    return amount * pct // 1000000