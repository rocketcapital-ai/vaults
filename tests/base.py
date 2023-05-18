import decimal
from brownie import Router, RequestManager, Processor, Vault, MyERC20, DefaultBlacklistPolicy, TestERC20
from brownie import BlacklistPolicyWhitelist, ShareTaxPolicyVanilla, BlacklistPolicyManual
from brownie import accounts, reverts, project, chain
from utils import *


class BaseTest:
    def setup_default_blacklist(self):
        self.before_setup_hook()
        assert len(accounts) >= 10, "Please run test with at least 10 accounts."
        self.admin, self.client1, self.client2, self.client3, self.client4, self.client5 = accounts[0:6]
        self.fee_collector, self.dydx_delegate, self.usdc_source, self.tax_collector = accounts[6:10]
        self.zero_address = "0x" + ("00" * 20)
        self.max_uint = 2 ** 256 - 1
        self.chain_testing = False
        self.active_client = self.client1
        self.other_client = self.client2
        self.receiving_client = self.client3
        self.default_blacklist_policy = DefaultBlacklistPolicy.deploy(fr(self.admin))
        self.request_manager_impl = RequestManager.deploy(fr(self.admin))
        self.processor_impl = Processor.deploy(fr(self.admin))
        self.onboarding_fee_pct = int(dec("0.01e6"))
        self.withdrawal_fee_pct = int(dec("0.01e6"))

        try:
            ERC20 = op.ERC20
            self.usdc = ERC20.at(USDC_ADDR)
        except Exception:  # ValueError: # `.at` raises `ValueError` if no bytecode exists.
            self.usdc = MyERC20.deploy("My Circle Dollar", "USDC", int(1e18), self.usdc_source, fr(self.admin))

        self.router = Router.deploy(self.default_blacklist_policy, {'from': self.admin})

        self.vault = Vault.deploy(
            "LONG FUND",  # name_
            "yLONG",  # symbol_
            self.usdc,  # usdcTokenAddress_
            self.dydx_delegate,  # dydxDelegate_
            self.default_blacklist_policy,  # blacklistPolicy_
            self.request_manager_impl,
            self.processor_impl,
            self.onboarding_fee_pct,
            self.withdrawal_fee_pct,
            fr(self.admin)
        )

        self.vault.updateRouter(self.router, {'from': self.admin})
        self.router.authorizeVault(self.vault, {'from': self.admin})

        self.single_unit = self.vault.singleUnit()

        # supply testing accounts with AUM token funds
        starting_capital = 500000
        self.usdc.transfer(self.client1, int(starting_capital * 1e6), fr(self.usdc_source))
        self.usdc.transfer(self.client2, int(starting_capital * 1e6), fr(self.usdc_source))
        self.usdc.transfer(self.client3, int(starting_capital * 1e6), fr(self.usdc_source))
        self.usdc.transfer(self.client4, int(starting_capital * 1e6), fr(self.usdc_source))
        self.usdc.transfer(self.client5, int(starting_capital * 1e6), fr(self.usdc_source))

        self.deposit_request_mgr = RequestManager.at(self.vault.pendingDepositUsdc())
        self.withdraw_request_mgr = RequestManager.at(self.vault.pendingWithdrawShare())
        self.withdraw_processor = Processor.at(self.vault.pendingWithdrawUsdc())

        self.after_setup_hook()

    def setup_whitelist(self):
        self.before_setup_hook()
        assert len(accounts) >= 10, "Please run test with at least 10 accounts."
        self.admin, self.client1, self.client2, self.client3, self.client4, self.client5 = accounts[0:6]
        self.fee_collector, self.dydx_delegate, self.usdc_source, self.tax_collector = accounts[6:10]
        self.zero_address = "0x" + ("00" * 20)
        self.max_uint = 2 ** 256 - 1
        self.chain_testing = False
        self.active_client = self.client1
        self.other_client = self.client2
        self.receiving_client = self.client3
        self.default_blacklist_policy = BlacklistPolicyWhitelist.deploy(fr(self.admin))
        self.request_manager_impl = RequestManager.deploy(fr(self.admin))
        self.processor_impl = Processor.deploy(fr(self.admin))
        self.onboarding_fee_pct = int(dec("0.01e6"))
        self.withdrawal_fee_pct = int(dec("0.01e6"))

        try:
            ERC20 = op.ERC20
            self.usdc = ERC20.at(USDC_ADDR)
        except Exception:  # ValueError: # `.at` raises `ValueError` if no bytecode exists.
            self.usdc = TestERC20.deploy("My Circle Dollar", "USDC", self.default_blacklist_policy, self.admin, fr(self.admin))


        self.default_blacklist_policy.updateWhitelist(self.usdc_source, True, fr(self.admin))
        self.default_blacklist_policy.updateWhitelist(self.admin, True, fr(self.admin))
        self.usdc.mint(self.usdc_source, int(1e18))


        self.router = Router.deploy(self.default_blacklist_policy, {'from': self.admin})

        self.vault = Vault.deploy(
            "LONG FUND",  # name_
            "yLONG",  # symbol_
            self.usdc,  # usdcTokenAddress_
            self.dydx_delegate,  # dydxDelegate_
            self.default_blacklist_policy,  # blacklistPolicy_
            self.request_manager_impl,
            self.processor_impl,
            self.onboarding_fee_pct,
            self.withdrawal_fee_pct,
            fr(self.admin)
        )

        self.vault.updateRouter(self.router, {'from': self.admin})
        self.router.authorizeVault(self.vault, {'from': self.admin})

        self.default_blacklist_policy.updateWhitelist(self.vault, True, fr(self.admin))
        self.default_blacklist_policy.updateWhitelist(self.router, True, fr(self.admin))
        self.default_blacklist_policy.updateWhitelist(self.vault.pendingDepositUsdc(), True, fr(self.admin))
        self.default_blacklist_policy.updateWhitelist(self.vault.pendingWithdrawShare(), True, fr(self.admin))
        self.default_blacklist_policy.updateWhitelist(self.vault.pendingWithdrawUsdc(), True, fr(self.admin))


        self.single_unit = self.vault.singleUnit()

        # supply testing accounts with AUM token funds
        starting_capital = 500000
        self.usdc.transfer(self.client1, int(starting_capital * 1e6), fr(self.usdc_source))
        self.usdc.transfer(self.client2, int(starting_capital * 1e6), fr(self.usdc_source))
        self.usdc.transfer(self.client3, int(starting_capital * 1e6), fr(self.usdc_source))
        self.usdc.transfer(self.client4, int(starting_capital * 1e6), fr(self.usdc_source))
        self.usdc.transfer(self.client5, int(starting_capital * 1e6), fr(self.usdc_source))

        self.deposit_request_mgr = RequestManager.at(self.vault.pendingDepositUsdc())
        self.withdraw_request_mgr = RequestManager.at(self.vault.pendingWithdrawShare())
        self.withdraw_processor = Processor.at(self.vault.pendingWithdrawUsdc())

        self.after_setup_hook()

    def setup_method(self):
        self.setup_default_blacklist()

    def before_setup_hook(self):
        pass

    def after_setup_hook(self):
        pass

    def d2u(self, dec_amt: Decimal):  # decimal_to_uint
        uint = int((dec_amt * self.single_unit).quantize(Decimal("1"), rounding=decimal.ROUND_DOWN))
        verify(True, uint >= 0, "Cannot pass negative value here.")
        return uint

    def u2d(self, uint: int or str): # uint_to_decimal
        uint = dec(uint).quantize(Decimal("1"), rounding=decimal.ROUND_DOWN)
        verify(True, uint >= 0, "Cannot pass negative value here.")
        return uint / self.single_unit

    def usdc2shares(self, usdc_in: int, nav: int):
        return usdc_in * self.single_unit // nav

    def shares2usdc(self, shares_in: int, nav: int):
        return shares_in * nav // self.single_unit

    def print_all_balances(self, user):
        header = f"\n===== User: {user} ====="
        print(header)
        print(f"USDC Balance: {self.u2d(self.usdc.balanceOf(user))}")
        print(f"pUSDC Balance: {self.u2d(self.deposit_request_mgr.balanceOf(user))}")
        print(f"yShare Balance: {self.u2d(self.vault.balanceOf(user))}")
        print(f"pShare Balance: {self.u2d(self.withdraw_request_mgr.balanceOf(user))}")
        print(f"pw-USDC Balance: {self.u2d(self.withdraw_processor.balanceOf(user))}")
        print("=" * len(header))

    def print_total_supplies(self):
        header = f"\n===== TOTAL SUPPLIES ====="
        print(header)
        print(f"pUSDC Supplies: {self.u2d(self.deposit_request_mgr.totalSupply())}")
        print(f"yShare Supplies: {self.u2d(self.vault.totalSupply())}")
        print(f"pShare Supplies: {self.u2d(self.withdraw_request_mgr.totalSupply())}")
        print(f"pw-USDC Supplies: {self.u2d(self.withdraw_processor.totalSupply())}")
        print(f"VAULT USDC Balance: {self.u2d(self.usdc.balanceOf(self.vault))}")
        print("=" * len(header))

    def print_outstanding_holders(self):
        header = f"\n===== TOKEN HOLDERS ====="
        print(f"pUSDC {self.deposit_request_mgr.numberOfShareHolders()}")
        print(self.deposit_request_mgr.getShareHolders(0, self.deposit_request_mgr.numberOfShareHolders()))
        print(f"yShare {self.vault.numberOfShareHolders()}")
        print(self.vault.getShareHolders(0, self.vault.numberOfShareHolders()))
        print(f"pShare {self.withdraw_request_mgr.numberOfShareHolders()}")
        print(self.withdraw_request_mgr.getShareHolders(0, self.withdraw_request_mgr.numberOfShareHolders()))
        print(f"pw-USDC {self.withdraw_processor.numberOfShareHolders()}")
        print(self.withdraw_processor.getShareHolders(0, self.withdraw_processor.numberOfShareHolders()))
        print("=" * len(header))