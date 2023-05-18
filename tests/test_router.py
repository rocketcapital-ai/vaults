from base import *

class TestVault(BaseTest):
    def before_setup_hook(self):
        pass

    def after_setup_hook(self):
        self.vault2 = Vault.deploy(
            "SHORT FUND",  # name_
            "ySHORT",  # symbol_
            self.usdc,  # usdcTokenAddress_
            self.dydx_delegate,  # dydxDelegate_
            self.default_blacklist_policy,  # blacklistPolicy_
            self.request_manager_impl,
            self.processor_impl,
            self.onboarding_fee_pct,
            self.withdrawal_fee_pct,
            fr(self.admin)
        )
        self.vault2.updateRouter(self.router, fr(self.admin))

        self.usdc.approve(self.router, self.max_uint, fr(self.client1))
        self.usdc.approve(self.router, self.max_uint, fr(self.client2))
        self.vault.approve(self.router, self.max_uint, fr(self.client1))
        self.vault.approve(self.router, self.max_uint, fr(self.client2))

    def test_update_blacklist_policy(self):
        self.blacklist_policy = BlacklistPolicyManual.deploy(fr(self.admin))
        with reverts(): self.router.updateBlacklistPolicyAddress(self.client1, fr(self.admin))
        with reverts(): self.router.updateBlacklistPolicyAddress(self.blacklist_policy, fr(self.client1))
        self.router.updateBlacklistPolicyAddress(self.blacklist_policy, fr(self.admin))
        verify(self.blacklist_policy.address, self.router.blacklistPolicy())

        amount = 100000000
        self.blacklist_policy.updateBlacklist(self.client1, 1, fr(self.admin))
        with reverts(): self.router.depositRequest(self.vault, amount, self.client2, fr(self.client1))

        self.router.deauthorizeVault(self.vault, fr(self.admin))
        with reverts(): self.router.depositRequest(self.vault, amount, self.client2, fr(self.client1))
        self.router.authorizeVault(self.vault, fr(self.admin))

        with reverts(): self.router.depositRequest(self.vault, amount, self.client2, fr(self.client1))
        self.blacklist_policy.updateBlacklist(self.client1, 0, fr(self.admin))
        self.router.depositRequest(self.vault, amount, self.client2, fr(self.client1))
        self.vault.completeDeposits(1000000, [[self.client2, amount]])

        self.router.deauthorizeVault(self.vault, fr(self.admin))
        with reverts(): self.router.withdrawRequest(self.vault, amount, self.client1, fr(self.client2))
        self.router.authorizeVault(self.vault, fr(self.admin))

        self.blacklist_policy.updateBlacklist(self.client2, 1, fr(self.admin))
        with reverts(): self.router.withdrawRequest(self.vault, amount, self.client1, fr(self.client2))
        self.blacklist_policy.updateBlacklist(self.client2, 0, fr(self.admin))
        exp_fee = amount * self.onboarding_fee_pct // self.single_unit
        amount -= exp_fee
        self.router.withdrawRequest(self.vault, amount, self.client1, fr(self.client2))

    def test_deauthorize_authorize_vault(self):
        verify(1, self.router.numberOfAuthorizedVaults())
        verify(self.vault.address, self.router.getAuthorizedVault(0))

        with reverts(): self.router.authorizeVault(self.client1, fr(self.admin))
        with reverts(): self.router.authorizeVault(self.vault2, fr(self.client1))
        with reverts(): self.router.deauthorizeVault(self.vault2, fr(self.admin))

        self.router.authorizeVault(self.vault2, fr(self.admin))
        verify(self.max_uint, self.usdc.allowance(self.router, self.vault2.pendingDepositUsdc()))
        verify(self.max_uint, self.vault2.allowance(self.router, self.vault2.pendingWithdrawShare()))
        verify(2, self.router.numberOfAuthorizedVaults())
        verify(self.vault.address, self.router.getAuthorizedVault(0))
        verify(self.vault2.address, self.router.getAuthorizedVault(1))
        self.router.deauthorizeVault(self.vault2, fr(self.admin))
        verify(0, self.usdc.allowance(self.router, self.vault2.pendingDepositUsdc()))
        verify(0, self.vault2.allowance(self.router, self.vault2.pendingWithdrawShare()))
        verify(1, self.router.numberOfAuthorizedVaults())
        verify(self.vault.address, self.router.getAuthorizedVault(0))








