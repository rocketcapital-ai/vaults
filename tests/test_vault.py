from base import *

class TestVault(BaseTest):
    def before_setup_hook(self):
        pass

    def after_setup_hook(self):
        pass

    def test_update_competition(self):
        with reverts():
            self.vault.updateCompetition(self.zero_address, fr(self.admin))
        with reverts():
            self.vault.updateCompetition(self.client1, fr(self.client1))
        self.vault.updateCompetition(self.client1, fr(self.admin))
        verify(self.client1, self.vault.competition())
        self.vault.updateCompetition(self.dydx_delegate, fr(self.admin))
        verify(self.dydx_delegate, self.vault.competition())

    def test_update_onboarding_fee_collector(self):
        existing = self.vault.onboardingFeeCollector()
        with reverts():
            self.vault.updateOnboardingFeeCollector(self.zero_address, fr(self.admin))
        with reverts():
            self.vault.updateOnboardingFeeCollector(self.client1, fr(self.client1))
        self.vault.updateOnboardingFeeCollector(self.client1, fr(self.admin))
        verify(self.client1, self.vault.onboardingFeeCollector())
        self.vault.updateOnboardingFeeCollector(self.dydx_delegate, fr(self.admin))
        verify(self.dydx_delegate, self.vault.onboardingFeeCollector())
        self.vault.updateOnboardingFeeCollector(existing, fr(self.admin))

    def test_update_onboarding_fee_percentage(self):
        existing = self.vault.onboardingFeePercentage()
        pct = int(dec("0.2e6"))
        with reverts():
            self.vault.updateOnboardingFeePercentage(pct, fr(self.client1))
        self.vault.updateOnboardingFeePercentage(pct, fr(self.admin))
        verify(pct, self.vault.onboardingFeePercentage())
        self.vault.updateOnboardingFeePercentage(0, fr(self.admin))
        verify(0, self.vault.onboardingFeePercentage())
        self.vault.updateOnboardingFeePercentage(existing, fr(self.admin))

    def test_update_withdrawal_fee_collector(self):
        existing = self.vault.withdrawalFeeCollector()
        with reverts():
            self.vault.updateWithdrawalFeeCollector(self.zero_address, fr(self.admin))
        with reverts():
            self.vault.updateWithdrawalFeeCollector(self.client1, fr(self.client1))
        self.vault.updateWithdrawalFeeCollector(self.client1, fr(self.admin))
        verify(self.client1, self.vault.withdrawalFeeCollector())
        self.vault.updateWithdrawalFeeCollector(self.dydx_delegate, fr(self.admin))
        verify(self.dydx_delegate, self.vault.withdrawalFeeCollector())
        self.vault.updateWithdrawalFeeCollector(existing, fr(self.admin))

    def test_update_withdrawal_fee_percentage(self):
        existing = self.vault.withdrawalFeePercentage()
        pct = int(dec("0.2e6"))
        with reverts():
            self.vault.updateWithdrawalFeePercentage(pct, fr(self.client1))
        self.vault.updateWithdrawalFeePercentage(pct, fr(self.admin))
        verify(pct, self.vault.withdrawalFeePercentage())
        self.vault.updateWithdrawalFeePercentage(0, fr(self.admin))
        verify(0, self.vault.withdrawalFeePercentage())
        self.vault.updateWithdrawalFeePercentage(existing, fr(self.admin))



    def test_update_delegate_wallet(self):
        with reverts():
            self.vault.updateDelegateWallet(self.zero_address, fr(self.admin))
        with reverts():
            self.vault.updateDelegateWallet(self.client1, fr(self.client1))
        self.vault.updateDelegateWallet(self.client1, fr(self.admin))
        verify(self.client1, self.vault.delegateWallet())
        self.vault.updateDelegateWallet(self.dydx_delegate, fr(self.admin))
        verify(self.dydx_delegate, self.vault.delegateWallet())

    def test_complete_deposit(self):
        usdc_deposit_amt = self.usdc.balanceOf(self.client1) // 2
        new_nav = 1234567
        self.usdc.approve(self.router, self.max_uint, fr(self.client1))

        usdc_bef_bal_client1 = self.usdc.balanceOf(self.client1)
        usdc_bef_bal_vault = self.usdc.balanceOf(self.vault)
        with reverts(): self.router.depositRequest(self.vault, usdc_deposit_amt, self.zero_address, fr(self.client1))
        self.router.depositRequest(self.vault, usdc_deposit_amt, self.client1, fr(self.client1))
        usdc_aft_bal_client1 = self.usdc.balanceOf(self.client1)
        usdc_aft_bal_vault = self.usdc.balanceOf(self.vault)
        verify(usdc_deposit_amt, usdc_bef_bal_client1 - usdc_aft_bal_client1)
        verify(usdc_deposit_amt, usdc_aft_bal_vault - usdc_bef_bal_vault)

        # test refund
        usdc_bef_bal_client1 = self.usdc.balanceOf(self.client1)
        usdc_bef_bal_vault = self.usdc.balanceOf(self.vault)
        p_usdc_supply_bef = self.deposit_request_mgr.totalSupply()

        refund_amt = usdc_deposit_amt // 2
        with reverts(): self.vault.refundSingleDeposit(refund_amt, self.client1, fr(self.client1))
        self.vault.refundSingleDeposit(refund_amt, self.client1, fr(self.admin))
        usdc_aft_bal_client1 = self.usdc.balanceOf(self.client1)
        usdc_aft_bal_vault = self.usdc.balanceOf(self.vault)
        p_usdc_supply_aft = self.deposit_request_mgr.totalSupply()
        verify(refund_amt, usdc_aft_bal_client1 - usdc_bef_bal_client1)
        verify(refund_amt, usdc_bef_bal_vault - usdc_aft_bal_vault)
        verify(refund_amt, p_usdc_supply_bef - p_usdc_supply_aft)
        self.router.depositRequest(self.vault, refund_amt, self.client1, fr(self.client1))

        share_bef_bal_client1 = self.vault.balanceOf(self.client1)
        pd_bef_bal_client1 = self.deposit_request_mgr.balanceOf(self.client1)
        bef_share_supply = self.vault.totalSupply()
        with reverts(): self.vault.completeDeposits(new_nav, [[self.client2, 1]], fr(self.admin))
        with reverts(): self.vault.completeDeposits(new_nav, [[self.client1, 0]], fr(self.admin))
        self.vault.completeDeposits(new_nav, [[self.client1, usdc_deposit_amt - 1000000]], fr(self.admin))
        self.vault.completeDeposits(new_nav, [[self.client1, 1000000]], fr(self.admin))
        with reverts(): self.vault.completeDeposits(new_nav, [[self.client1, 1]], fr(self.admin))

        aft_share_supply = self.vault.totalSupply()
        share_aft_bal_client1 = self.vault.balanceOf(self.client1)
        pd_aft_bal_client1 = self.deposit_request_mgr.balanceOf(self.client1)
        verify(usdc_deposit_amt, pd_bef_bal_client1 - pd_aft_bal_client1)
        exp_fees = (usdc_deposit_amt - 1000000) * self.onboarding_fee_pct // self.single_unit
        exp_shares = (usdc_deposit_amt - 1000000 - exp_fees) * 1000000 // new_nav

        exp_fees = 1000000 * self.onboarding_fee_pct // self.single_unit
        exp_shares += (1000000 - exp_fees) * 1000000 // new_nav

        verify(exp_shares, share_aft_bal_client1 - share_bef_bal_client1)
        verify(exp_shares, aft_share_supply - bef_share_supply)

    def test_complete_withdrawal(self):
        usdc_deposit_amt = self.usdc.balanceOf(self.client1) // 2
        new_nav = 1234567
        self.usdc.approve(self.router, self.max_uint, fr(self.client1))
        self.router.depositRequest(self.vault, usdc_deposit_amt, self.client1, fr(self.client1))
        self.vault.completeDeposits(new_nav, [[self.client1, usdc_deposit_amt]], fr(self.admin))
        self.vault.approve(self.router, self.max_uint, fr(self.client1))

        vault_bef_bal_client1 = self.vault.balanceOf(self.client1)
        vault_bef_bal_vault = self.vault.balanceOf(self.vault)
        ps_bef_bal_client1 = self.withdraw_request_mgr.balanceOf(self.client1)
        ps_bef_supply, pw_bef_supply = self.withdraw_request_mgr.totalSupply(), self.withdraw_processor.totalSupply()
        amt_shares = vault_bef_bal_client1
        with reverts(): self.router.withdrawRequest(self.vault, amt_shares, self.zero_address, fr(self.client1))
        self.router.withdrawRequest(self.vault, amt_shares, self.client1, fr(self.client1))
        vault_aft_bal_client1 = self.vault.balanceOf(self.client1)
        vault_aft_bal_vault = self.vault.balanceOf(self.vault)
        ps_aft_bal_client1 = self.withdraw_request_mgr.balanceOf(self.client1)
        ps_aft_supply, pw_aft_supply = self.withdraw_request_mgr.totalSupply(), self.withdraw_processor.totalSupply()
        verify(amt_shares, vault_bef_bal_client1 - vault_aft_bal_client1)
        verify(amt_shares, vault_aft_bal_vault - vault_bef_bal_vault)
        verify(amt_shares, ps_aft_bal_client1 - ps_bef_bal_client1)
        verify(amt_shares, ps_aft_supply - ps_bef_supply)
        verify(pw_bef_supply, pw_aft_supply)

        # test refund
        share_bef_bal_client1 = self.vault.balanceOf(self.client1)
        share_bef_bal_vault = self.vault.balanceOf(self.vault)
        p_share_supply_bef = self.withdraw_request_mgr.totalSupply()
        p_share_bef_client1 = self.withdraw_request_mgr.balanceOf(self.client1)
        refund_amt = amt_shares // 2
        with reverts(): self.vault.refundSingleWithdrawal(refund_amt, self.client1, fr(self.client1))
        self.vault.refundSingleWithdrawal(refund_amt, self.client1, fr(self.admin))
        share_aft_bal_client1 = self.vault.balanceOf(self.client1)
        share_aft_bal_vault = self.vault.balanceOf(self.vault)
        p_share_supply_aft = self.withdraw_request_mgr.totalSupply()
        p_share_aft_client1 = self.withdraw_request_mgr.balanceOf(self.client1)
        verify(refund_amt, share_aft_bal_client1 - share_bef_bal_client1)
        verify(refund_amt, share_bef_bal_vault - share_aft_bal_vault)
        verify(refund_amt, p_share_supply_bef - p_share_supply_aft)
        verify(refund_amt, p_share_bef_client1 - p_share_aft_client1)
        self.router.withdrawRequest(self.vault, refund_amt, self.client1, fr(self.client1))

        # Process Withdrawal
        share_bef_bal_client1 = self.vault.balanceOf(self.client1)
        ps_bef_bal_client1 = self.withdraw_request_mgr.balanceOf(self.client1)
        pw_bef_bal_client1 = self.withdraw_processor.balanceOf(self.client1)
        bef_share_supply = self.vault.totalSupply()
        ps_bef_supply, pw_bef_supply = self.withdraw_request_mgr.totalSupply(), self.withdraw_processor.totalSupply()
        with reverts(): self.vault.processWithdrawals(new_nav, [[self.client2, 1]], fr(self.admin))
        with reverts(): self.vault.processWithdrawals(new_nav, [[self.client1, 0]], fr(self.admin))
        self.vault.processWithdrawals(new_nav, [[self.client1, amt_shares - 1000000]], fr(self.admin))
        self.vault.processWithdrawals(new_nav, [[self.client1, 1000000]], fr(self.admin))
        with reverts(): self.vault.processWithdrawals(new_nav, [[self.client1, 1]], fr(self.admin))
        aft_share_supply = self.vault.totalSupply()
        share_aft_bal_client1 = self.vault.balanceOf(self.client1)
        ps_aft_bal_client1 = self.withdraw_request_mgr.balanceOf(self.client1)
        pw_aft_bal_client1 = self.withdraw_processor.balanceOf(self.client1)
        ps_aft_supply, pw_aft_supply = self.withdraw_request_mgr.totalSupply(), self.withdraw_processor.totalSupply()
        verify(amt_shares, ps_bef_bal_client1 - ps_aft_bal_client1)
        verify(share_bef_bal_client1, share_aft_bal_client1)
        verify(amt_shares, ps_bef_supply - ps_aft_supply)
        verify(amt_shares, bef_share_supply - aft_share_supply)

        exp_usdc = (amt_shares - 1000000) * new_nav // 1000000
        exp_usdc += 1000000 * new_nav // 1000000
        verify(exp_usdc, pw_aft_bal_client1 - pw_bef_bal_client1)
        verify(exp_usdc, pw_aft_supply - pw_bef_supply)

        # Complete Withdrawal
        usdc_bef_bal_client1 = self.usdc.balanceOf(self.client1)
        pw_bef_bal_client1 = self.withdraw_processor.balanceOf(self.client1)
        amt_usdc = pw_bef_bal_client1
        bef_share_supply = self.vault.totalSupply()
        ps_bef_supply, pw_bef_supply = self.withdraw_request_mgr.totalSupply(), self.withdraw_processor.totalSupply()
        with reverts(): self.vault.completeWithdrawals([[self.client2, 1]], fr(self.admin))
        with reverts(): self.vault.completeWithdrawals([[self.client1, 0]], fr(self.admin))
        self.vault.completeWithdrawals([[self.client1, amt_usdc - 1000000]], fr(self.admin))
        self.vault.completeWithdrawals([[self.client1, 1000000]], fr(self.admin))
        with reverts(): self.vault.completeWithdrawals([[self.client1, 1]], fr(self.admin))

        usdc_aft_bal_client1 = self.usdc.balanceOf(self.client1)
        pw_aft_bal_client1 = self.withdraw_processor.balanceOf(self.client1)
        aft_share_supply = self.vault.totalSupply()
        ps_aft_supply, pw_aft_supply = self.withdraw_request_mgr.totalSupply(), self.withdraw_processor.totalSupply()
        exp_fees = amt_usdc * self.withdrawal_fee_pct // self.single_unit

        verify(amt_usdc, pw_bef_bal_client1 - pw_aft_bal_client1)
        verify(amt_usdc, pw_bef_supply - pw_aft_supply)
        verify(amt_usdc - exp_fees, usdc_aft_bal_client1 - usdc_bef_bal_client1)
        verify(bef_share_supply, aft_share_supply)
        verify(ps_bef_supply, ps_aft_supply)


    def test_share_tax(self):
        tax_pct1 = int(dec("0.22e6"))
        tax_pct2 = int(dec("0.07e6"))
        share_tax_policy = ShareTaxPolicyVanilla.deploy(self.fee_collector, self.tax_collector, tax_pct1, tax_pct2, 6, fr(self.admin))
        share_tax_policy.updateExempt(self.withdraw_request_mgr, True, fr(self.admin))
        share_tax_policy.updateExempt(self.router, True, fr(self.admin))
        verify(self.zero_address, self.vault.shareTaxPolicy())
        with reverts(): self.vault.updateShareTaxPolicyAddress(self.client1, fr(self.admin))
        with reverts(): self.vault.updateShareTaxPolicyAddress(share_tax_policy, fr(self.client1))
        self.vault.updateShareTaxPolicyAddress(share_tax_policy, fr(self.admin))
        verify(share_tax_policy, self.vault.shareTaxPolicy())

        self.usdc.transfer(self.client1, int(1000 * 1e6), fr(self.usdc_source))
        usdc_deposit_amt = self.usdc.balanceOf(self.client1) // 2

        # check that minting is not affected by share tax
        self.usdc.approve(self.router, self.max_uint, fr(self.client1))
        client1_share_bef = self.vault.balanceOf(self.client1)
        client1_usdc_bef = self.usdc.balanceOf(self.client1)
        bef_fee_collector = self.vault.balanceOf(self.fee_collector)
        bef_tax_collector = self.vault.balanceOf(self.tax_collector)
        self.router.depositRequest(self.vault, usdc_deposit_amt, self.client1, fr(self.client1))
        self.vault.completeDeposits(1000000, [[self.client1, usdc_deposit_amt]], fr(self.admin))
        client1_share_aft = self.vault.balanceOf(self.client1)
        client1_usdc_aft = self.usdc.balanceOf(self.client1)
        aft_fee_collector = self.vault.balanceOf(self.fee_collector)
        aft_tax_collector = self.vault.balanceOf(self.tax_collector)
        exp_fees = self.onboarding_fee_pct * usdc_deposit_amt // self.single_unit
        verify(usdc_deposit_amt - exp_fees, client1_share_aft - client1_share_bef)
        verify(usdc_deposit_amt, client1_usdc_bef - client1_usdc_aft)
        verify(aft_fee_collector, bef_fee_collector)
        verify(aft_tax_collector, bef_tax_collector)

        # Test base erc20 functions.
        with reverts(): self.vault.approve(self.zero_address, self.max_uint, fr(self.client1))
        with reverts(): self.vault.transferFrom(self.zero_address, self.client1, 0, fr(self.client1))
        with reverts(): self.vault.transferFrom(self.zero_address, self.client1, 1, fr(self.client1))
        with reverts(): self.vault.transfer(self.zero_address, 1, fr(self.client1))

        num_shareholders = self.vault.numberOfShareHolders()
        shareholders = set(self.vault.getShareHolders(0, num_shareholders))
        verify(1, num_shareholders)
        verify({self.client1}, shareholders)
        share_bal = self.vault.balanceOf(self.client1)
        trf_amt = share_bal // 2
        exp_tax_1 = trf_amt * tax_pct1 // 1000000
        exp_tax_2 = trf_amt * tax_pct2 // 1000000
        bef_client1 = self.vault.balanceOf(self.client1)
        bef_client2 = self.vault.balanceOf(self.client2)
        bef_fee_collector = self.vault.balanceOf(self.fee_collector)
        bef_tax_collector = self.vault.balanceOf(self.tax_collector)

        test_phase = True
        try: self.default_blacklist_policy.isWhitelisted(self.vault)
        except: test_phase = False

        if test_phase:
            with reverts(): self.vault.transfer(self.client2, trf_amt, fr(self.client1))
            num_shareholders = self.vault.numberOfShareHolders()
            shareholders = set(self.vault.getShareHolders(0, num_shareholders))
            verify(1, num_shareholders)
            verify({self.client1}, shareholders)

        else:
            self.vault.transfer(self.client2, trf_amt, fr(self.client1))
            aft_client1 = self.vault.balanceOf(self.client1)
            aft_client2 = self.vault.balanceOf(self.client2)
            aft_fee_collector = self.vault.balanceOf(self.fee_collector)
            aft_tax_collector = self.vault.balanceOf(self.tax_collector)
            verify(trf_amt + exp_tax_1 + exp_tax_2, bef_client1 - aft_client1)
            verify(trf_amt, aft_client2 - bef_client2)
            verify(exp_tax_1, aft_fee_collector - bef_fee_collector)
            verify(exp_tax_2, aft_tax_collector - bef_tax_collector)
            num_shareholders = self.vault.numberOfShareHolders()
            shareholders = set(self.vault.getShareHolders(0, num_shareholders))
            verify(4, num_shareholders)
            verify({self.client1, self.client2, self.fee_collector, self.tax_collector}, shareholders)

        # check that burning is not affected by share tax
        withdraw_amt = self.vault.balanceOf(self.client1) // 2
        self.vault.approve(self.router, self.max_uint, fr(self.client1))
        client1_share_bef = self.vault.balanceOf(self.client1)
        client1_usdc_bef = self.usdc.balanceOf(self.client1)
        bef_fee_collector = self.vault.balanceOf(self.fee_collector)
        bef_tax_collector = self.vault.balanceOf(self.tax_collector)
        self.router.withdrawRequest(self.vault, withdraw_amt, self.client1, fr(self.client1))
        self.vault.processWithdrawals(1000000, [[self.client1, withdraw_amt]], fr(self.admin))
        self.vault.completeWithdrawals([[self.client1, withdraw_amt]], fr(self.admin))
        client1_share_aft = self.vault.balanceOf(self.client1)
        client1_usdc_aft = self.usdc.balanceOf(self.client1)
        aft_fee_collector = self.vault.balanceOf(self.fee_collector)
        aft_tax_collector = self.vault.balanceOf(self.tax_collector)
        exp_fees = self.withdrawal_fee_pct * withdraw_amt // self.single_unit
        verify(withdraw_amt - exp_fees, client1_usdc_aft - client1_usdc_bef)
        verify(withdraw_amt, client1_share_bef - client1_share_aft)
        verify(aft_fee_collector, bef_fee_collector)
        verify(aft_tax_collector, bef_tax_collector)

        # test no fees for vip sender
        share_bal = self.vault.balanceOf(self.client1)
        with reverts(): self.vault.transfer(self.client2, share_bal, fr(self.client1))
        share_tax_policy.updateVip(self.client1, True, fr(self.admin))
        if test_phase:
            with reverts(): self.vault.transfer(self.client2, share_bal, fr(self.client1))
            num_shareholders = self.vault.numberOfShareHolders()
            shareholders = set(self.vault.getShareHolders(0, num_shareholders))
            verify(1, num_shareholders)
            verify({self.client1}, shareholders)

        else:
            self.vault.transfer(self.client2, share_bal, fr(self.client1))
            num_shareholders = self.vault.numberOfShareHolders()
            shareholders = set(self.vault.getShareHolders(0, num_shareholders))
            verify(3, num_shareholders)
            verify({self.client2, self.fee_collector, self.tax_collector}, shareholders)

        self.vault.updateShareTaxPolicyAddress(self.zero_address, fr(self.admin))
        verify(False, self.vault.transferFeeActive())

    def test_settlement_in_out(self):
        usdc_deposit_amt = self.usdc.balanceOf(self.client1) // 2
        if self.usdc.balanceOf(self.vault) == 0:
            self.usdc.approve(self.router, self.max_uint, fr(self.client1))
            self.router.depositRequest(self.vault, usdc_deposit_amt, self.client1, fr(self.client1))

        new_usdc_deposit_amt = self.usdc.balanceOf(self.vault)
        assert new_usdc_deposit_amt >= usdc_deposit_amt

        with reverts():
            self.vault.settlementOut(new_usdc_deposit_amt, fr(self.client1))

        with reverts():
            self.vault.settlementOut(new_usdc_deposit_amt + 1, fr(self.admin))

        usdc_bef_bal_delegate = self.usdc.balanceOf(self.dydx_delegate)
        usdc_bef_bal_vault = self.usdc.balanceOf(self.vault)
        self.vault.settlementOut(new_usdc_deposit_amt, fr(self.admin))
        usdc_aft_bal_delegate = self.usdc.balanceOf(self.dydx_delegate)
        usdc_aft_bal_vault = self.usdc.balanceOf(self.vault)
        verify(new_usdc_deposit_amt, usdc_aft_bal_delegate - usdc_bef_bal_delegate)
        verify(new_usdc_deposit_amt, usdc_bef_bal_vault - usdc_aft_bal_vault)

        self.usdc.transfer(self.dydx_delegate, self.usdc.balanceOf(self.client2) // 2, fr(self.usdc_source))
        in_amount = self.usdc.balanceOf(self.dydx_delegate)
        usdc_bef_bal_delegate = self.usdc.balanceOf(self.dydx_delegate)
        usdc_bef_bal_vault = self.usdc.balanceOf(self.vault)
        with reverts():
            self.vault.settlementIn(in_amount, fr(self.client1))
        with reverts():
            self.vault.settlementIn(in_amount, fr(self.admin))
        self.usdc.approve(self.vault, self.max_uint, fr(self.dydx_delegate))
        self.vault.settlementIn(in_amount, fr(self.admin))
        usdc_aft_bal_delegate = self.usdc.balanceOf(self.dydx_delegate)
        usdc_aft_bal_vault = self.usdc.balanceOf(self.vault)
        verify(in_amount, usdc_bef_bal_delegate - usdc_aft_bal_delegate)
        verify(in_amount, usdc_aft_bal_vault - usdc_bef_bal_vault)

    def test_manual_mint(self):
        shares_to_mint = 1000 * 1000000
        bef_shares, bef_share_supply = self.vault.balanceOf(self.client1), self.vault.totalSupply()
        with reverts(): self.vault.manualMint(shares_to_mint, self.client1, fr(self.client1))
        self.vault.manualMint(shares_to_mint, self.client1, fr(self.admin))
        aft_shares, aft_share_supply = self.vault.balanceOf(self.client1), self.vault.totalSupply()

        verify(shares_to_mint, aft_shares - bef_shares)
        verify(shares_to_mint, aft_share_supply - bef_share_supply)
