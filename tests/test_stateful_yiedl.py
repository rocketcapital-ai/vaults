import json
from collections import defaultdict
from brownie.test import strategy
from utils import *
from brownie import Router, RequestManager, Processor, Vault, MyERC20, DefaultBlacklistPolicy, ShareTaxPolicyVanilla, BlacklistPolicyManual
from brownie import accounts, reverts, project, chain


class Balances:
    vault_usdc: int
    vault_shares: int
    pd_supply: int
    pws_supply: int
    pw_supply: int
    share_supply: int


class YiedlStateMachine:
    address = strategy('address')
    deposit_amt = strategy('uint256', min_value=1, max_value=2000000 * 1000000)
    withdraw_amt = strategy('uint256', min_value=1, max_value=50000 * 1000000)
    min_amt = strategy('uint256', min_value=0, max_value=1000 * 1000000)
    nav = strategy('uint256', min_value=100000, max_value=5000000)
    sender_idx = strategy('uint8', min_value=1, max_value=4)
    receiver_idx = strategy('uint8', min_value=1, max_value=4)

    def __init__(self, accounts, router, request_manager, processor, vault, myerc20, default_blacklist_policy,
                 share_tax_policy_vanilla, blakclist_policy_manual):
        assert len(accounts) >= 10, "Please run test with at least 10 accounts."
        self.admin, self.client1, self.client2, self.client3, self.client4, self.client5 = accounts[0:6]
        self.fee_collector, self.dydx_delegate, self.usdc_source, self.tax_collector = accounts[6:10]
        self.zero_address = "0x" + ("00" * 20)
        self.max_uint = 2 ** 256 - 1
        self.clients = [self.client1, self.client2, self.client3, self.client4, self.client5]
        self.default_blacklist_policy = default_blacklist_policy.deploy(fr(self.admin))
        self.request_manager_impl = request_manager.deploy(fr(self.admin))
        self.processor_impl = processor.deploy(fr(self.admin))
        self.dydx_off_chain_bal = 0
        self.onboarding_fee_pct = int(dec("0.01e6"))
        self.withdrawal_fee_pct = int(dec("0.01e6"))

        try:
            ERC20 = project.load("OpenZeppelin//openzeppelin-contracts@4.8.0").ERC20
            self.usdc = ERC20.at(USDC_ADDR)
        except Exception:  # ValueError: # `.at` raises `ValueError` if no bytecode exists.
            self.usdc = myerc20.deploy("My Circle Dollar", "USDC", int(1e18), self.usdc_source, fr(self.admin))

        self.router = router.deploy(self.default_blacklist_policy, {'from': self.admin})

        self.vault = vault.deploy(
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
        self.vault.updateOnboardingFeeCollector(self.fee_collector, {'from': self.admin})
        self.vault.updateWithdrawalFeeCollector(self.fee_collector, {'from': self.admin})

        self.single_unit = self.vault.singleUnit()
        self.usdc.approve(self.vault, self.max_uint, fr(self.dydx_delegate))

        # supply testing accounts with AUM token funds
        starting_capital = 5000000
        for user in self.clients:
            self.usdc.increaseAllowance(self.router, self.max_uint, fr(user))
            self.vault.increaseAllowance(self.router, self.max_uint, fr(user))
            self.usdc.transfer(user, int(starting_capital * 1e6), fr(self.usdc_source))

        self.deposit_request_mgr = request_manager.at(self.vault.pendingDepositUsdc())
        self.withdraw_request_mgr = request_manager.at(self.vault.pendingWithdrawShare())
        self.withdraw_processor = processor. at(self.vault.pendingWithdrawUsdc())

        # deploy and link share tax policy
        tax_pct1 = int(dec("0.22e6"))
        tax_pct2 = int(dec("0.07e6"))
        self.share_tax_policy = share_tax_policy_vanilla.deploy(self.fee_collector, self.tax_collector, tax_pct1, tax_pct2,
                                                             6,
                                                             fr(self.admin))
        self.share_tax_policy.updateVip(self.fee_collector, True, fr(self.admin))
        self.share_tax_policy.updateVip(self.tax_collector, True, fr(self.admin))
        self.share_tax_policy.updateExempt(self.withdraw_request_mgr, True, fr(self.admin))
        self.share_tax_policy.updateExempt(self.router, True, fr(self.admin))
        self.vault.updateShareTaxPolicyAddress(self.share_tax_policy, fr(self.admin))

        # Deploy but don't link blacklist policy
        self.blacklist_policy = blakclist_policy_manual.deploy(fr(self.admin))

        print(self.clients)

    def setup(self):
        self.pd_holders = set()
        self.pws_holders = set()
        self.pw_holders = set()
        self.share_holders = set()
        self.blacklisted = set()
        self.request_records = defaultdict(lambda: [])
        self.processed_records = defaultdict(lambda: [])

    def get_balances(self) -> Balances:
        balances = Balances()
        balances.vault_usdc = self.usdc.balanceOf(self.vault)
        balances.vault_shares = self.vault.balanceOf(self.vault)
        balances.pd_supply = self.deposit_request_mgr.totalSupply()
        balances.pws_supply = self.withdraw_request_mgr.totalSupply()
        balances.pw_supply = self.withdraw_processor.totalSupply()
        balances.share_supply = self.vault.totalSupply()
        return balances

    def add_and_check_records(self,
                              user, is_request, vault, request_type,
                              sender, receiver, timestamp, amount,
                              amount_in, amount_out, fees_paid):
        if is_request:
            new_record = RequestRecord([
                vault, request_type, sender, receiver, timestamp, amount
            ])
            self.request_records[user].append(new_record)
        else:
            new_record = ProcessedRecord([
                vault, request_type, receiver, timestamp, amount_in, amount_out, fees_paid
            ])
            self.processed_records[user].append(new_record)

        self.check_records(user)

    def check_records(self, user):
        num_request, num_processed = self.router.numberOfRecords(user)
        requests, processed = self.router.getRecords(user, 0, num_request, 0, num_processed)

        for i in range(0, len(requests)):
            verify(self.request_records[user][i].to_list(), requests[i])

        for i in range(0, len(processed)):
            verify(self.processed_records[user][i].to_list(), processed[i])


    def rule_set_minimum_deposit(self, min_amt):
        with reverts(): self.deposit_request_mgr.updateMinimumDeposit(min_amt, fr(self.client1))
        self.deposit_request_mgr.updateMinimumDeposit(min_amt, fr(self.admin))
        verify(min_amt, self.deposit_request_mgr.minimumDeposit())

    def rule_set_minimum_withdrawal(self, min_amt):
        with reverts(): self.withdraw_request_mgr.updateMinimumDeposit(min_amt, fr(self.client1))
        self.withdraw_request_mgr.updateMinimumDeposit(min_amt, fr(self.admin))
        verify(min_amt, self.withdraw_request_mgr.minimumDeposit())

    def rule_deposit(self, sender_idx, receiver_idx, deposit_amt):
        sender, receiver = self.clients[sender_idx], self.clients[receiver_idx]
        sender_bal = self.usdc.balanceOf(sender)
        if sender_bal < deposit_amt:
            self.usdc.transfer(sender, deposit_amt, fr(self.usdc_source))
        sender_usdc_bef, receiver_pd_bef = self.usdc.balanceOf(sender), self.deposit_request_mgr.balanceOf(receiver)
        bef = self.get_balances()

        with reverts(): self.router.depositRequest(self.zero_address, deposit_amt, receiver, fr(sender))

        if deposit_amt < self.deposit_request_mgr.minimumDeposit():
            with reverts(): self.router.depositRequest(self.vault, deposit_amt, receiver, fr(sender))
            return

        if (sender in self.blacklisted) or (receiver in self.blacklisted):
            with reverts(): self.router.depositRequest(self.vault, deposit_amt, receiver, fr(sender))
            return

        tx = self.router.depositRequest(self.vault, deposit_amt, receiver, fr(sender))
        self.add_and_check_records(receiver, True, self.vault,
                                   REQUEST_TYPE.DEPOSIT, sender, receiver,
                                   tx.timestamp, deposit_amt, None, None, None)
        if sender != receiver:
            self.add_and_check_records(sender, True, self.vault,
                                       REQUEST_TYPE.DEPOSIT, sender, receiver,
                                       tx.timestamp, deposit_amt, None, None, None)

        sender_usdc_aft, receiver_pd_aft = self.usdc.balanceOf(sender), self.deposit_request_mgr.balanceOf(receiver)
        aft = self.get_balances()
        verify(deposit_amt, sender_usdc_bef - sender_usdc_aft)
        verify(deposit_amt, receiver_pd_aft - receiver_pd_bef)
        verify(deposit_amt, aft.vault_usdc - bef.vault_usdc)
        verify(deposit_amt, aft.pd_supply - bef.pd_supply)
        verify(aft.share_supply, bef.share_supply)
        verify(aft.vault_shares, bef.vault_shares)
        verify(aft.pw_supply, bef.pw_supply)
        verify(aft.pws_supply, bef.pws_supply)

        self.pd_holders.add(receiver)

        print("after deposit", deposit_amt, aft.vault_usdc)

    def rule_complete_deposit(self, nav):
        pd_supply = self.deposit_request_mgr.totalSupply()
        num_pd_holders = self.deposit_request_mgr.numberOfShareHolders()
        if pd_supply == 0:
            verify(0, num_pd_holders)
            with reverts():
                self.deposit_request_mgr.getShareHolders(0, 1)
            return

        verify(self.pd_holders, set(self.deposit_request_mgr.getShareHolders(0, num_pd_holders)))
        verify(len(self.pd_holders), num_pd_holders)
        users_and_usdc_amounts = []
        old_dydx_off_cahin_bal = self.dydx_off_chain_bal
        for holder in self.pd_holders:
            pd_bal = self.deposit_request_mgr.balanceOf(holder)
            if pd_bal > self.dydx_off_chain_bal:
                break
            self.dydx_off_chain_bal -= pd_bal
            users_and_usdc_amounts.append([holder, pd_bal])
        bef_shares, exp_shares = {}, {}
        blacklisted_users = 0
        fees = 0
        for user, amount in users_and_usdc_amounts:
            bef_shares[user] = self.vault.balanceOf(user)
            fee = calculate_fee(self.onboarding_fee_pct, amount)
            fees += fee
            exp_shares[user] = (amount - fee) * self.single_unit // nav
            if user in self.blacklisted: blacklisted_users += 1
        bef = self.get_balances()

        if blacklisted_users > 0:
            with reverts(): self.vault.completeDeposits(nav, users_and_usdc_amounts, fr(self.admin))
            self.dydx_off_chain_bal = old_dydx_off_cahin_bal
            return

        print(users_and_usdc_amounts)
        print("fees", fees)
        print("vault balance", self.usdc.balanceOf(self.vault))
        bef_fee_collector = self.usdc.balanceOf(self.fee_collector)
        tx = self.vault.completeDeposits(nav, users_and_usdc_amounts, fr(self.admin))
        aft_fee_collector = self.usdc.balanceOf(self.fee_collector)
        fees = 0
        for user, amount in users_and_usdc_amounts:
            fees_paid = calculate_fee(self.onboarding_fee_pct, amount)
            fees += fees_paid
            shares_out = (amount - fees_paid) * self.single_unit // nav
            self.add_and_check_records(user, False, self.vault, REQUEST_TYPE.DEPOSIT,
                                       None, user, tx.timestamp, None, amount - fees_paid, shares_out, fees_paid)

        aft = self.get_balances()

        total_pd_burned, total_shares_minted = 0, 0
        for user, amount in users_and_usdc_amounts:
            aft_shares = self.vault.balanceOf(user)
            aft_pd = self.deposit_request_mgr.balanceOf(user)
            verify(exp_shares[user], aft_shares - bef_shares[user])
            verify(0, aft_pd)
            total_pd_burned += amount
            total_shares_minted += exp_shares[user]
            self.pd_holders.discard(user)
            if self.vault.balanceOf(user) > 0:
                self.share_holders.add(user)

        verify(fees, aft_fee_collector - bef_fee_collector)
        verify(aft.vault_usdc, bef.vault_usdc - fees)
        verify(total_shares_minted, aft.share_supply - bef.share_supply)
        verify(total_pd_burned, bef.pd_supply - aft.pd_supply)
        verify(aft.vault_shares, bef.vault_shares)
        verify(aft.pws_supply, bef.pws_supply)
        verify(aft.pw_supply, bef.pw_supply)

        print("pd_supply", aft.pd_supply)

    def rule_withdraw(self, sender_idx, receiver_idx, withdraw_amt):
        sender, receiver = self.clients[sender_idx], self.clients[receiver_idx]
        sender_shares_bef, receiver_pws_bef = self.vault.balanceOf(sender), self.withdraw_request_mgr.balanceOf(receiver)
        bef = self.get_balances()

        with reverts(): self.router.withdrawRequest(self.zero_address, withdraw_amt, receiver, fr(sender))

        if sender_shares_bef < withdraw_amt:
            with reverts(): self.router.withdrawRequest(self.vault, withdraw_amt, receiver, fr(sender))
            return

        if withdraw_amt < self.withdraw_request_mgr.minimumDeposit():
            with reverts(): self.router.withdrawRequest(self.vault, withdraw_amt, receiver, fr(sender))
            return

        if (sender in self.blacklisted) or (receiver in self.blacklisted):
            with reverts(): self.router.withdrawRequest(self.vault, withdraw_amt, receiver, fr(sender))
            return

        tx = self.router.withdrawRequest(self.vault, withdraw_amt, receiver, fr(sender))
        self.add_and_check_records(receiver, True, self.vault, REQUEST_TYPE.WITHDRAW,
                                   sender, receiver, tx.timestamp,
                                   withdraw_amt, None, None, None)
        if sender != receiver:
            self.add_and_check_records(sender, True, self.vault, REQUEST_TYPE.WITHDRAW,
                                       sender, receiver, tx.timestamp,
                                       withdraw_amt, None, None, None)

        sender_shares_aft, receiver_pws_aft = self.vault.balanceOf(sender), self.withdraw_request_mgr.balanceOf(receiver)
        aft = self.get_balances()
        verify(withdraw_amt, sender_shares_bef - sender_shares_aft)
        verify(withdraw_amt, receiver_pws_aft - receiver_pws_bef)
        verify(withdraw_amt, aft.vault_shares - bef.vault_shares)
        verify(withdraw_amt, aft.pws_supply - bef.pws_supply)
        verify(aft.share_supply, bef.share_supply)
        verify(aft.vault_usdc, bef.vault_usdc)
        verify(aft.pd_supply, bef.pd_supply)

        self.pws_holders.add(receiver)
        self.share_holders.add(self.vault.address)
        if self.vault.balanceOf(sender) == 0:
            self.share_holders.discard(sender)

    def rule_process_withdrawal(self, nav):
        pws_supply = self.withdraw_request_mgr.totalSupply()
        num_pws_holders = self.withdraw_request_mgr.numberOfShareHolders()
        if pws_supply == 0:
            verify(0, num_pws_holders)
            with reverts():
                self.withdraw_request_mgr.getShareHolders(0, 1)
            print("Nothing to withdraw.", self.get_balances().vault_usdc)
            return

        verify(self.pws_holders, set(self.withdraw_request_mgr.getShareHolders(0, num_pws_holders)))
        verify(len(self.pws_holders), num_pws_holders)
        bef_pw, exp_pw = {}, {}
        users_and_share_amounts = []
        old_dydx_off_chain_balance = self.dydx_off_chain_bal
        blacklisted_users = 0
        for holder in self.pws_holders:
            pws_bal = self.withdraw_request_mgr.balanceOf(holder)
            exp_pw[holder] = pws_bal * nav // self.single_unit
            bef_pw[holder] = self.withdraw_processor.balanceOf(holder)
            self.dydx_off_chain_bal += exp_pw[holder]
            users_and_share_amounts.append([holder, pws_bal])
            if holder in self.blacklisted: blacklisted_users += 1

        if blacklisted_users > 0:
            with reverts(): self.vault.processWithdrawals(nav, users_and_share_amounts, fr(self.admin))
            self.dydx_off_chain_bal = old_dydx_off_chain_balance
            return

        bef = self.get_balances()
        tx = self.vault.processWithdrawals(nav, users_and_share_amounts, fr(self.admin))
        for user, share_amt in users_and_share_amounts:
            exp_usdc = share_amt * nav // self.single_unit
            fees_paid = calculate_fee(self.withdrawal_fee_pct, exp_usdc)
            self.add_and_check_records(user, False, self.vault, REQUEST_TYPE.WITHDRAW,
                                       None, user, tx.timestamp, None,
                                       share_amt, exp_usdc - fees_paid, fees_paid)

        aft = self.get_balances()

        total_pws_burned, total_pw_minted = 0, 0
        for user, amount in users_and_share_amounts:
            aft_pws = self.withdraw_request_mgr.balanceOf(user)
            aft_pw = self.withdraw_processor.balanceOf(user)
            verify(exp_pw[user], aft_pw - bef_pw[user])
            verify(0, aft_pws)
            total_pws_burned += amount
            total_pw_minted += exp_pw[user]
            self.pws_holders.discard(user)

            if self.withdraw_processor.balanceOf(user) > 0:
                self.pw_holders.add(user)

        if self.vault.balanceOf(self.vault) == 0:
            self.share_holders.discard(self.vault.address)

        verify(aft.vault_usdc, bef.vault_usdc)
        verify(total_pw_minted, aft.pw_supply - bef.pw_supply)
        verify(total_pws_burned, bef.pws_supply - aft.pws_supply)
        verify(total_pws_burned, bef.vault_shares - aft.vault_shares)
        verify(total_pws_burned, bef.share_supply - aft.share_supply)
        verify(aft.pd_supply, bef.pd_supply)

    def rule_complete_withdrawal(self):
        pw_supply = self.withdraw_processor.totalSupply()
        num_pw_holders = self.withdraw_processor.numberOfShareHolders()
        if pw_supply == 0:
            verify(0, num_pw_holders)
            with reverts():
                self.withdraw_processor.getShareHolders(0, 1)
            return

        verify(self.pw_holders, set(self.withdraw_processor.getShareHolders(0, num_pw_holders)))
        verify(len(self.pw_holders), num_pw_holders)

        users_and_amounts = []
        total_usdc = 0
        bef = self.get_balances()
        bef_usdc = {}
        blacklisted_users = 0
        for holder in self.pw_holders:
            if holder in self.blacklisted: blacklisted_users += 1
            pw_bal = self.withdraw_processor.balanceOf(holder)
            total_usdc += pw_bal
            if total_usdc > bef.vault_usdc:
                total_usdc -= pw_bal
                break
            users_and_amounts.append([holder, pw_bal])
            bef_usdc[holder] = self.usdc.balanceOf(holder)

        if blacklisted_users > 0:
            with reverts(): self.vault.completeWithdrawals(users_and_amounts, fr(self.admin))
            return

        bef_fee_collector = self.usdc.balanceOf(self.fee_collector)
        self.vault.completeWithdrawals(users_and_amounts, fr(self.admin))
        aft_fee_collector = self.usdc.balanceOf(self.fee_collector)

        fees = 0
        for user, amount in users_and_amounts:
            fee = calculate_fee(self.withdrawal_fee_pct, amount)
            fees += fee
            verify(0, self.withdraw_processor.balanceOf(user))
            verify(amount - fee, self.usdc.balanceOf(user) - bef_usdc[user])
            self.pw_holders.discard(user)

        aft = self.get_balances()
        verify(fees, aft_fee_collector - bef_fee_collector)
        verify(total_usdc, bef.vault_usdc - aft.vault_usdc)
        verify(total_usdc, bef.pw_supply - aft.pw_supply)
        verify(aft.vault_shares, bef.vault_shares)
        verify(aft.pws_supply, bef.pws_supply)
        verify(aft.pd_supply, bef.pd_supply)
        verify(aft.share_supply, bef.share_supply)

    def rule_settlement_out(self):
        pd_bal = self.deposit_request_mgr.totalSupply()

        # leave money in the vault to pay fees.
        fees = calculate_fee(self.onboarding_fee_pct, pd_bal)
        pd_bal -= fees

        delegate_bef, vault_bef = self.usdc.balanceOf(self.dydx_delegate), self.usdc.balanceOf(self.vault)
        if pd_bal > self.dydx_off_chain_bal:
            to_trf = pd_bal - self.dydx_off_chain_bal
            with reverts(): self.vault.settlementOut(to_trf, fr(self.client1))
            print("settlement out:", to_trf, "current_bal", vault_bef, end=" ")
            self.vault.settlementOut(to_trf, fr(self.admin))
            self.dydx_off_chain_bal += to_trf
            delegate_aft, vault_aft = self.usdc.balanceOf(self.dydx_delegate), self.usdc.balanceOf(self.vault)
            verify(to_trf, delegate_aft - delegate_bef)
            verify(to_trf, vault_bef - vault_aft)

    def rule_settlement_in(self):
        pw_bal = self.withdraw_processor.totalSupply()
        if pw_bal <= self.usdc.balanceOf(self.vault):
            return
        to_trf = pw_bal - self.usdc.balanceOf(self.vault)
        self.usdc.transfer(self.dydx_delegate, to_trf, fr(self.usdc_source))
        print("settlement in:", to_trf, end=" ")
        delegate_bef, vault_bef = self.usdc.balanceOf(self.dydx_delegate), self.usdc.balanceOf(self.vault)
        verify_gte(self.dydx_off_chain_bal, to_trf)
        self.dydx_off_chain_bal -= to_trf
        with reverts(): self.vault.settlementIn(to_trf, fr(self.client1))
        self.vault.settlementIn(to_trf, fr(self.admin))
        delegate_aft, vault_aft = self.usdc.balanceOf(self.dydx_delegate), self.usdc.balanceOf(self.vault)
        verify(to_trf, delegate_bef - delegate_aft)
        verify(to_trf, vault_aft - vault_bef)

    def rule_transfer_tax(self, receiver_idx):
        if len(self.share_holders) == 0: return
        share_holders = self.share_holders.copy()
        share_holders.discard(self.vault.address)
        if len(share_holders) == 0: return
        sender = list(share_holders)[0]
        receiver = self.clients[receiver_idx]
        if receiver == sender:
            receiver = self.clients[(receiver_idx + 1) % len(self.clients)]

        trf_amt = self.vault.balanceOf(sender) // 2
        exp_tax_1 = trf_amt * self.share_tax_policy.federalTaxPercentage() // self.single_unit
        exp_tax_2 = trf_amt * self.share_tax_policy.stateTaxPercentage() // self.single_unit
        bef_sender = self.vault.balanceOf(sender)
        bef_receiver = self.vault.balanceOf(receiver)
        bef_fee_collector = self.vault.balanceOf(self.fee_collector)
        bef_tax_collector = self.vault.balanceOf(self.tax_collector)

        if (sender in self.blacklisted) or (receiver in self.blacklisted):
            with reverts(): self.vault.transfer(receiver, trf_amt, fr(sender))
            return

        self.vault.transfer(receiver, trf_amt, fr(sender))
        aft_sender = self.vault.balanceOf(sender)
        aft_receiver = self.vault.balanceOf(receiver)
        aft_fee_collector = self.vault.balanceOf(self.fee_collector)
        aft_tax_collector = self.vault.balanceOf(self.tax_collector)
        verify(trf_amt + exp_tax_1 + exp_tax_2, bef_sender - aft_sender)
        verify(trf_amt, aft_receiver - bef_receiver)
        verify(exp_tax_1, aft_fee_collector - bef_fee_collector)
        verify(exp_tax_2, aft_tax_collector - bef_tax_collector)

        # check that the fee/tax collectors can transfer with no tax
        bef_sender = self.vault.balanceOf(sender)
        bef_receiver = self.vault.balanceOf(receiver)
        sender_trf_amt = self.vault.balanceOf(self.fee_collector)
        receiver_trf_amt = self.vault.balanceOf(self.tax_collector)
        self.vault.transfer(sender, sender_trf_amt, fr(self.fee_collector))
        self.vault.transfer(receiver, receiver_trf_amt, fr(self.tax_collector))
        verify(0, self.vault.balanceOf(self.fee_collector))
        verify(0, self.vault.balanceOf(self.tax_collector))
        aft_sender = self.vault.balanceOf(sender)
        aft_receiver = self.vault.balanceOf(receiver)
        verify(sender_trf_amt, aft_sender - bef_sender)
        verify(receiver_trf_amt, aft_receiver - bef_receiver)

        if self.vault.balanceOf(sender) > 0: self.share_holders.add(sender)
        else: self.share_holders.discard(sender)
        if self.vault.balanceOf(receiver) > 0: self.share_holders.add(receiver)
        else: self.share_holders.discard(receiver)

        verify(self.withdraw_request_mgr.totalSupply(), self.vault.balanceOf(self.vault))

    def rule_blacklist(self, sender_idx):
        user = self.clients[sender_idx]
        # Link blacklist policy
        if self.vault.blacklistPolicy() == self.default_blacklist_policy:
            with reverts(): self.vault.updateBlacklistPolicyAddress(self.blacklist_policy, fr(user))
            self.vault.updateBlacklistPolicyAddress(self.blacklist_policy, fr(self.admin))
            with reverts(): self.router.updateBlacklistPolicyAddress(self.blacklist_policy, fr(user))
            self.router.updateBlacklistPolicyAddress(self.blacklist_policy, fr(self.admin))

        # toggle user
        if user in self.blacklisted:
            with reverts(): self.blacklist_policy.updateBlacklist(user, False, fr(user))
            self.blacklist_policy.updateBlacklist(user, False, fr(self.admin))
            verify(False, self.blacklist_policy.isBlacklisted(user))
            self.blacklisted.discard(user)
        else:
            with reverts(): self.blacklist_policy.updateBlacklist(user, True, fr(user))
            self.blacklist_policy.updateBlacklist(user, True, fr(self.admin))
            verify(True, self.blacklist_policy.isBlacklisted(user))
            self.blacklisted.add(user)


    def invariant_no_usdc_in_intermediate_contracts(self):
        verify(0, self.usdc.balanceOf(self.router))
        verify(0, self.usdc.balanceOf(self.deposit_request_mgr))
        verify(0, self.usdc.balanceOf(self.withdraw_request_mgr))
        verify(0, self.usdc.balanceOf(self.withdraw_processor))
        verify(0, self.usdc.balanceOf(self.default_blacklist_policy))
        # verify(0, self.usdc.balanceOf(self.share_tax_policy))

    def invariant_no_shares_in_intermediate_contracts(self):
        verify(0, self.vault.balanceOf(self.router))
        verify(0, self.vault.balanceOf(self.deposit_request_mgr))
        verify(0, self.vault.balanceOf(self.withdraw_request_mgr))
        verify(0, self.vault.balanceOf(self.withdraw_processor))
        verify(0, self.vault.balanceOf(self.default_blacklist_policy))

    def invariant_holders_tally(self):
        num_share_holders = self.deposit_request_mgr.numberOfShareHolders()
        verify(self.pd_holders, set(self.deposit_request_mgr.getShareHolders(0, num_share_holders)))
        verify(len(self.pd_holders), num_share_holders)

        num_pws_holders = self.withdraw_request_mgr.numberOfShareHolders()
        verify(self.pws_holders, set(self.withdraw_request_mgr.getShareHolders(0, num_pws_holders)))
        verify(len(self.pws_holders), num_pws_holders)

        num_pw_holders = self.withdraw_processor.numberOfShareHolders()
        verify(self.pw_holders, set(self.withdraw_processor.getShareHolders(0, num_pw_holders)))
        verify(len(self.pw_holders), num_pw_holders)

        num_share_holders = self.vault.numberOfShareHolders()
        verify(self.share_holders, set(self.vault.getShareHolders(0, num_share_holders)))
        verify(len(self.share_holders), num_share_holders)

    def invariant_pws_vault_shares(self):
        verify(self.withdraw_request_mgr.totalSupply(), self.vault.balanceOf(self.vault))

def test_stateful_fund(accounts, Router, RequestManager, Processor, Vault, MyERC20, DefaultBlacklistPolicy, ShareTaxPolicyVanilla, BlacklistPolicyManual, state_machine):
    state_machine(YiedlStateMachine, accounts, Router, RequestManager, Processor, Vault, MyERC20, DefaultBlacklistPolicy, ShareTaxPolicyVanilla, BlacklistPolicyManual)



