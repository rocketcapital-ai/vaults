from brownie import RequestManager, RequestManagerDeployer, MyERC20, DefaultBlacklistPolicy
from brownie import accounts, reverts, project, chain
from utils import *


class TestERC4626:

    def setup_method(self):
        assert len(accounts) >= 10, "Please run test with at least 10 accounts."
        self.admin, self.client1, self.client2, self.client3, self.client4, self.client5 = accounts[0:6]
        self.fee_collector, self.vault_eoa, self.usdc_source, self.tax_collector = accounts[6:10]
        self.zero_address = "0x" + ("00" * 20)
        self.max_uint = 2 ** 256 - 1
        self.samples = 30
        self.name, self.symbol = "Request Manager", "RQM"
        self.default_blacklist_policy = DefaultBlacklistPolicy.deploy(fr(self.admin))
        try:
            ERC20 = project.load("OpenZeppelin//openzeppelin-contracts@4.8.0").ERC20
            self.usdc = ERC20.at(USDC_ADDR)
        except Exception:  # ValueError: # `.at` raises `ValueError` if no bytecode exists.
            self.usdc = MyERC20.deploy("My Circle Dollar", "USDC", int(1000000000000e6), self.usdc_source, fr(self.admin))

        self.usdc.transfer(self.client1, int(1000000e6), fr(self.usdc_source))
        self.request_manager_impl = RequestManager.deploy(fr(self.admin))

        self.rqm_deployer = RequestManagerDeployer.deploy(fr(self.admin))
        self.rqm_deployer.deployRequestManager(
            self.request_manager_impl, self.name, self.symbol, self.usdc,
            self.admin, self.admin,
            fr(self.admin)
        )
        self.request_manager = RequestManager.at(self.rqm_deployer.deployedAddresses(0))
        self.request_manager.grantRole(self.request_manager.RCI_INFLOW_MGR(), self.client1, fr(self.admin))
        self.request_manager.grantRole(self.request_manager.RCI_OUTFLOW_MGR(), self.client1, fr(self.admin))
        random.seed(1234567)

    def test_erc20_metadata(self):
        verify(self.name, self.request_manager.name())
        verify(self.symbol, self.request_manager.symbol())
        verify(6, self.request_manager.decimals())

    def test_asset(self):
        verify(self.usdc.address, self.request_manager.asset())

    def test_total_assets(self):
        verify(self.usdc.balanceOf(self.request_manager), self.request_manager.totalAssets())

    def test_convert_to_shares(self):
        for assets in [dec(0), dec(1), dec(10), dec(100), dec(1000000), dec(10000000), dec(100000000)]:
            exp_shares = assets
            verify(exp_shares, self.request_manager.convertToShares(assets))

    def test_convert_to_assets(self):
        for shares in [dec(0), dec(1), dec(10), dec('1e16'), dec('1e19'), dec('1e22')]:
            exp_assets = shares
            verify(exp_assets, self.request_manager.convertToAssets(shares))

    def test_max_deposit(self):
        verify(2 ** 256 - 1, self.request_manager.maxDeposit(self.client1))

        self.request_manager.updateGlobalMax(MAX_LIMIT_ID.DEPOSIT, 3000000000, fr(self.admin))
        verify(3000000000, self.request_manager.maxDeposit(self.client1))

        self.request_manager.updateIndividualMax(MAX_LIMIT_ID.DEPOSIT, self.client1, 100000000, fr(self.admin))
        verify(100000000, self.request_manager.maxDeposit(self.client1))

        self.request_manager.toggleSuspendSubscription(fr(self.admin))
        verify(0, self.request_manager.maxDeposit(self.client1))

    def test_preview_deposit(self):
        asset_list = [random.randint(100000, 200000000) for _ in range(self.samples)]
        for assets in asset_list:
            exp_shares = self.request_manager.convertToShares(assets)
            previewed_deposit = self.request_manager.previewDeposit(assets)
            verify(exp_shares, previewed_deposit)
            verify(self.request_manager.previewMint(previewed_deposit), assets)

            before_share_bal = self.request_manager.balanceOf(self.client1)
            self.usdc.increaseAllowance(self.request_manager, assets, fr(self.client1))
            self.request_manager.deposit(assets, self.client1, fr(self.client1))
            after_share_bal = self.request_manager.balanceOf(self.client1)
            verify(after_share_bal - before_share_bal, previewed_deposit)

    def test_deposit(self):
        asset_list = [random.randint(100000, 200000000) for _ in range(self.samples)]
        for assets in asset_list:
            self.usdc.transfer(self.client1, 200000000, fr(self.usdc_source))
            previewed_deposit = self.request_manager.previewDeposit(assets)

            before_share_bal = self.request_manager.balanceOf(self.client2)
            before_asset_bal = self.usdc.balanceOf(self.client1)
            self.usdc.increaseAllowance(self.request_manager, assets, fr(self.client1))
            tx = self.request_manager.deposit(assets, self.client2, fr(self.client1))
            after_share_bal = self.request_manager.balanceOf(self.client2)
            after_asset_bal = self.usdc.balanceOf(self.client1)
            verify(before_asset_bal - after_asset_bal, assets)
            verify(after_share_bal - before_share_bal, previewed_deposit)
            verify_event([('sender', self.client1.address),
                          ('owner', self.client2.address),
                          ('assets', assets),
                          ('shares', after_share_bal - before_share_bal)],
                         tx.events['Deposit'].items()
                         )
            verify(after_share_bal - before_share_bal, tx.return_value)

    def test_max_mint(self):
        verify(2 ** 256 - 1, self.request_manager.maxMint(self.client1))

        self.request_manager.updateGlobalMax(MAX_LIMIT_ID.MINT, int(dec('3000e6')), fr(self.admin))
        verify(int(dec('3000e6')), self.request_manager.maxMint(self.client1))

        self.request_manager.updateIndividualMax(MAX_LIMIT_ID.MINT, self.client1, int(dec('100e6')), fr(self.admin))
        verify(int(dec('100e6')), self.request_manager.maxMint(self.client1))

        self.request_manager.toggleSuspendSubscription(fr(self.admin))
        verify(0, self.request_manager.maxMint(self.client1))

    def test_preview_mint(self):
        share_list = [random.randint(100000, 20000000000) for _ in range(self.samples)]
        for shares in share_list:
            exp_assets = self.request_manager.convertToAssets(shares)
            previewed_mint = self.request_manager.previewMint(shares)
            verify(exp_assets, previewed_mint)
            verify(self.request_manager.previewDeposit(previewed_mint), shares)
            self.usdc.transfer(self.client1, exp_assets, fr(self.usdc_source))
            before_asset_bal = self.usdc.balanceOf(self.client1)
            self.usdc.increaseAllowance(self.request_manager, exp_assets, fr(self.client1))
            self.request_manager.mint(shares, self.client1, fr(self.client1))
            after_asset_bal = self.usdc.balanceOf(self.client1)
            verify(before_asset_bal - after_asset_bal, previewed_mint)

    def test_mint(self):
        share_list = [random.randint(100000, 20000000000) for _ in range(self.samples)]
        for shares in share_list:
            previewed_mint = self.request_manager.previewMint(shares)
            self.usdc.transfer(self.client1, previewed_mint, fr(self.usdc_source))
            before_share_bal = self.request_manager.balanceOf(self.client2)
            before_asset_bal = self.usdc.balanceOf(self.client1)
            self.usdc.increaseAllowance(self.request_manager, previewed_mint, fr(self.client1))
            tx = self.request_manager.mint(shares, self.client2, fr(self.client1))
            after_share_bal = self.request_manager.balanceOf(self.client2)
            after_asset_bal = self.usdc.balanceOf(self.client1)
            verify(before_asset_bal - after_asset_bal, previewed_mint)
            verify(after_share_bal - before_share_bal, shares)
            verify_event([('sender', self.client1.address),
                          ('owner', self.client2.address),
                          ('assets', before_asset_bal - after_asset_bal),
                          ('shares', shares)],
                         tx.events['Deposit'].items()
                         )
            verify(before_asset_bal - after_asset_bal, tx.return_value)

    def test_max_withdraw(self):
        shares = 20000000
        self.usdc.increaseAllowance(self.request_manager, shares, fr(self.client1))
        self.request_manager.mint(shares, self.client1, fr(self.client1))
        verify(0, self.request_manager.maxWithdraw(self.client1))

        self.request_manager.updateGlobalMax(MAX_LIMIT_ID.WITHDRAW, int(dec('10e6')), fr(self.admin))
        verify(0, self.request_manager.maxWithdraw(self.client1))

        self.request_manager.updateIndividualMax(MAX_LIMIT_ID.WITHDRAW, self.client1, int(dec('100e6')), fr(self.admin))
        verify(0, self.request_manager.maxWithdraw(self.client1))

        self.request_manager.toggleSuspendRedemption(fr(self.admin))
        verify(0, self.request_manager.maxWithdraw(self.client1))

    def test_preview_withdraw(self):
        asset_list = [random.randint(100000, 20000000000) for _ in range(self.samples)]
        asset_list.append(0)
        for assets in asset_list:
            if assets > 0:
                with reverts(): self.request_manager.previewWithdraw(assets)
                continue
            previewed_withdraw = self.request_manager.previewWithdraw(assets)
            verify(assets, self.request_manager.previewRedeem(previewed_withdraw))

            before_share_bal = self.request_manager.balanceOf(self.client1)
            self.request_manager.withdraw(assets, self.client1, self.client1, fr(self.client1))
            after_share_bal = self.request_manager.balanceOf(self.client1)
            verify(before_share_bal - after_share_bal, previewed_withdraw)

    def test_withdraw(self):
        shares = 20000000
        self.usdc.increaseAllowance(self.request_manager, shares, fr(self.client1))
        self.request_manager.mint(shares, self.client1, fr(self.client1))
        self.request_manager.approve(self.client1, self.max_uint, fr(self.client3))
        asset_list = [shares // 2, 0]
        for assets in asset_list:
            if assets > 0:
                with reverts(): self.request_manager.withdraw(assets, self.client2, self.client3, fr(self.client1))
                continue

            previewed_withdraw = self.request_manager.previewWithdraw(assets)
            before_asset_bal = self.usdc.balanceOf(self.client2)
            before_share_bal_sender = self.request_manager.balanceOf(self.client1)
            before_share_bal = self.request_manager.balanceOf(self.client3)
            tx = self.request_manager.withdraw(assets, self.client2, self.client3, fr(self.client1))
            after_asset_bal = self.usdc.balanceOf(self.client2)
            after_share_bal_sender = self.request_manager.balanceOf(self.client1)
            after_share_bal = self.request_manager.balanceOf(self.client3)
            verify(after_asset_bal - before_asset_bal, assets)
            verify(before_share_bal - after_share_bal, previewed_withdraw)
            verify(0, before_share_bal_sender - after_share_bal_sender)

            verify_event([('sender', self.client1.address),
                          ('receiver', self.client2.address),
                          ('owner', self.client3.address),
                          ('assets', assets),
                          ('shares', before_share_bal - after_share_bal)],
                         tx.events['Withdraw'].items()
                         )
            verify(tx.return_value, before_share_bal - after_share_bal)

    def test_max_redeem(self):
        shares = 20000000
        self.usdc.increaseAllowance(self.request_manager, shares, fr(self.client1))
        self.request_manager.mint(shares, self.client1, fr(self.client1))

        share_bal = self.request_manager.balanceOf(self.client1)
        verify(share_bal, self.request_manager.maxRedeem(self.client1))

        self.request_manager.updateGlobalMax(MAX_LIMIT_ID.REDEEM, int(dec('10e6')), fr(self.admin))
        verify(min(int(dec('10e6')), share_bal), self.request_manager.maxRedeem(self.client1))

        self.request_manager.updateIndividualMax(MAX_LIMIT_ID.REDEEM, self.client1, int(dec('100e6')), fr(self.admin))
        verify(min(int(dec('100e6')), share_bal), self.request_manager.maxRedeem(self.client1))

        self.request_manager.toggleSuspendRedemption(fr(self.admin))
        verify(0, self.request_manager.maxRedeem(self.client1))

    def test_preview_redeem(self):
        share_list = [random.randint(100000, 20000000000) for _ in range(self.samples)]

        for shares in share_list:
            self.usdc.increaseAllowance(self.request_manager, shares, fr(self.client1))
            self.request_manager.mint(shares, self.client1, fr(self.client1))
            exp_assets = self.request_manager.convertToAssets(shares)
            verify(shares, self.request_manager.convertToShares(exp_assets))
            previewed_redeem = self.request_manager.previewRedeem(shares)
            verify(0, previewed_redeem)
            before_asset_bal = self.usdc.balanceOf(self.client2)
            self.request_manager.redeem(shares, self.client2, self.client1, fr(self.client1))
            after_asset_bal = self.usdc.balanceOf(self.client2)
            verify(after_asset_bal - before_asset_bal, previewed_redeem)

    def test_redeem(self):
        share_list = [random.randint(int(dec('0.1e6')), int(dec('200e6'))) for _ in range(self.samples)]
        for shares in share_list:
            self.usdc.increaseAllowance(self.request_manager, shares, fr(self.client1))
            self.request_manager.mint(shares, self.client3, fr(self.client1))
            previewed_redeem = self.request_manager.previewRedeem(shares)
            before_asset_bal = self.usdc.balanceOf(self.client2)
            before_share_bal_sender = self.request_manager.balanceOf(self.client1)
            before_share_bal = self.request_manager.balanceOf(self.client3)
            self.request_manager.increaseAllowance(self.client1, shares, fr(self.client3))
            tx = self.request_manager.redeem(shares, self.client2, self.client3, fr(self.client1))
            after_asset_bal = self.usdc.balanceOf(self.client2)
            after_share_bal_sender = self.request_manager.balanceOf(self.client1)
            after_share_bal = self.request_manager.balanceOf(self.client3)
            verify(after_asset_bal - before_asset_bal, previewed_redeem)
            verify(before_share_bal - after_share_bal, shares)
            verify(0, before_share_bal_sender - after_share_bal_sender)
            verify_event([('sender', self.client1.address),
                          ('receiver', self.client2.address),
                          ('owner', self.client3.address),
                          ('assets', after_asset_bal - before_asset_bal),
                          ('shares', shares)],
                         tx.events['Withdraw'].items()
                         )
            verify(tx.return_value, after_asset_bal - before_asset_bal)