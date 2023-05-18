//SPDX-License-Identifier: UNLICENSED

pragma solidity ^0.8.0;

import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/proxy/Clones.sol";
import "./ShareToken.sol";
import "./RequestManager.sol";
import "./Processor.sol";
import "./Types.sol";
import "./Router.sol";

contract Vault is ShareToken, Types {

    using SafeERC20 for IERC20Metadata;
    using Clones for address;

    address public usdcToken;
    address public delegateWallet;
    address public router;
    RequestManager public pendingDepositUsdc;
    RequestManager public pendingWithdrawShare;
    Processor public pendingWithdrawUsdc;

    uint256 public nav;
    uint256 constant public singleUnit = 10 ** 6;

    address public onboardingFeeCollector;
    uint256 public onboardingFeePercentage;
    address public withdrawalFeeCollector;
    uint256 public withdrawalFeePercentage;

    address public competition;

    constructor(string memory name_, string memory symbol_,
        address usdcToken_, address delegateWallet_,
        address blacklistPolicy_,
        address requestManagerImpl, address processorImpl,
        uint256 onboardingFeePercentage_, uint256 withdrawalFeePercentage_
    )
    ShareToken(name_, symbol_, blacklistPolicy_, msg.sender)
    {
        updateOnboardingFeeCollector(msg.sender);
        updateOnboardingFeePercentage(onboardingFeePercentage_);
        updateWithdrawalFeeCollector(msg.sender);
        updateWithdrawalFeePercentage(withdrawalFeePercentage_);

        pendingDepositUsdc = RequestManager(requestManagerImpl.clone());
        pendingDepositUsdc.setup(
            string.concat("Pending USDC deposit for ", name_), string.concat("pd-USDC"), usdcToken_, address(this), msg.sender
        );
        pendingDepositUsdc.grantRole(pendingDepositUsdc.RCI_OUTFLOW_MGR(), address(this));

        pendingWithdrawUsdc = Processor(processorImpl.clone());
        pendingWithdrawUsdc.setup(
            string.concat("Pending USDC withdraw for ", name_), string.concat("pw-USDC"),
                requestManagerImpl, symbol_, address(this), msg.sender
        );

        pendingWithdrawShare = pendingWithdrawUsdc.withdrawRequestManager();
        pendingWithdrawShare.grantRole(pendingWithdrawShare.RCI_OUTFLOW_MGR(), address(pendingWithdrawUsdc));
        pendingWithdrawShare.grantRole(pendingWithdrawShare.RCI_OUTFLOW_MGR(), address(this));

        usdcToken = usdcToken_;
        delegateWallet = delegateWallet_;
    }

    function completeSingleDeposit(uint256 pendingDepositUsdcAmt, address receiver)
    internal
    returns (uint256 feesInUsdc)
    {
        require(pendingDepositUsdcAmt > 0);

        feesInUsdc = calculateFee(pendingDepositUsdcAmt, onboardingFeePercentage);
        uint256 sharesToMint = (pendingDepositUsdcAmt - feesInUsdc) * singleUnit / nav;

        pendingDepositUsdc.redeem(pendingDepositUsdcAmt, address(this), receiver);
        require(blacklistPolicy.depositPolicy(pendingDepositUsdcAmt, sharesToMint, receiver, receiver), "Blacklisted deposit request.");
        shareMint(receiver, sharesToMint);

        Router(router).updateExchangeRecord(receiver, 0, receiver, pendingDepositUsdcAmt - feesInUsdc, sharesToMint, feesInUsdc);
        emit SharesMinted(receiver, sharesToMint);
    }

    function completeDeposits(uint256 newNav, UsersAndAmounts[] calldata usersAndAmountsUsdc)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        updateNav(newNav);
        uint256 total = 0;
        uint256 onboardingFees = 0;
        for (uint32 i = 0; i < usersAndAmountsUsdc.length; i++) {
            onboardingFees += completeSingleDeposit(usersAndAmountsUsdc[i].amount, usersAndAmountsUsdc[i].user);
        }

        IERC20Metadata(usdcToken).safeTransfer(onboardingFeeCollector, onboardingFees);
    }

    function refundSingleDeposit(uint256 amount, address requester)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        require(amount <= pendingDepositUsdc.balanceOf(requester), "Insufficient.");
        pendingDepositUsdc.redeem(amount, address(this), requester);
        IERC20Metadata(usdcToken).safeTransfer(requester, amount);

        Router(router).updateExchangeRecord(requester,  2, requester, 0, amount, 0);
    }

    function processSingleWithdrawal(
        uint256 pSharesIn, address receiver, uint256 withdrawNav,
        uint256 unitValue, address routerAddr, string memory symbol)
    internal
    returns (uint256 pwUsdcOut)
    {
        pwUsdcOut = pendingWithdrawUsdc.processSingleWithdrawal(pSharesIn, receiver, withdrawNav, unitValue);
        require(blacklistPolicy.withdrawPolicy(pwUsdcOut, pSharesIn, receiver, receiver), "Blacklisted withdraw request.");
        uint256 fee = calculateFee(pwUsdcOut, withdrawalFeePercentage);
        Router(routerAddr).updateExchangeRecord(receiver, 1, receiver, pSharesIn, pwUsdcOut - fee, fee);
    }

    function processWithdrawals(uint256 newNav, UsersAndAmounts[] memory usersAndAmountsShares)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        updateNav(newNav);
        uint256 unitValue = singleUnit;
        uint256 totalYShares = 0;
        address routerAddr = router;
        string memory symbol = symbol();
        for (uint32 i = 0; i < usersAndAmountsShares.length; i++) {
            processSingleWithdrawal(
                usersAndAmountsShares[i].amount,
                usersAndAmountsShares[i].user,
                newNav,
                unitValue,
                routerAddr,
                symbol
            );
            emit SharesBurned(usersAndAmountsShares[i].user, usersAndAmountsShares[i].amount);
            totalYShares += usersAndAmountsShares[i].amount;
        }
        burnShares(totalYShares);
    }

    function completeSingleWithdrawal(uint256 pendingWithdrawalUsdcAmt, address receiver)
    internal
    returns (uint256 feesInUsdc)
    {
        require(blacklistPolicy.withdrawPolicy(pendingWithdrawalUsdcAmt, 0, receiver, receiver), "Blacklisted withdraw completion.");
        pendingWithdrawUsdc.reclaimPwUsdc(pendingWithdrawalUsdcAmt, receiver);
        feesInUsdc = calculateFee(pendingWithdrawalUsdcAmt, withdrawalFeePercentage);
        IERC20Metadata(usdcToken).safeTransfer(receiver, pendingWithdrawalUsdcAmt - feesInUsdc);
    }

    function completeWithdrawals(UsersAndAmounts[] calldata usersAndAmountsUsdc)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        uint256 total = 0;
        uint256 withdrawalFees = 0;
        for (uint32 i = 0; i < usersAndAmountsUsdc.length; i++) {
            withdrawalFees += completeSingleWithdrawal(usersAndAmountsUsdc[i].amount, usersAndAmountsUsdc[i].user);
//            total += usersAndAmountsUsdc[i].amount;
        }

        IERC20Metadata(usdcToken).safeTransfer(withdrawalFeeCollector, withdrawalFees);
    }

    function refundSingleWithdrawal(uint256 amount, address requester)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        require(amount <= pendingWithdrawShare.balanceOf(requester), "Insufficient.");
        pendingWithdrawShare.redeem(amount, address(this), requester);
        IERC20Metadata(address(this)).safeTransfer(requester, amount);

        Router(router).updateExchangeRecord(requester, 3, requester, 0, amount, 0);
    }

    function manualMint(uint256 amount, address recipient)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        shareMint(recipient, amount);
        Router(router).updateExchangeRecord(recipient, 4, recipient, 0, amount, 0);
        emit SharesMinted(recipient, amount);
    }


    function updateDelegateWallet(address newDelegateWallet)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        require(newDelegateWallet != address(0));
        delegateWallet = newDelegateWallet;
    }

    function settlementOut(uint256 usdcAmount)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        IERC20Metadata(usdcToken).safeTransfer(delegateWallet, usdcAmount);
    }

    function settlementIn(uint256 usdcAmount)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        IERC20Metadata(usdcToken).safeTransferFrom(delegateWallet, address(this), usdcAmount);
    }

    function updateRouter(address newRouter)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        address oldRouter = router;
        if (oldRouter != address(0)) {
            pendingDepositUsdc.revokeRole(pendingDepositUsdc.RCI_INFLOW_MGR(), newRouter);
            pendingWithdrawShare.revokeRole(pendingWithdrawShare.RCI_INFLOW_MGR(), newRouter);
        }
        pendingDepositUsdc.grantRole(pendingDepositUsdc.RCI_INFLOW_MGR(), newRouter);
        pendingWithdrawShare.grantRole(pendingWithdrawShare.RCI_INFLOW_MGR(), newRouter);
        router = newRouter;
    }

    function updateNav(uint256 newNav)
    internal
    {
        if (newNav != nav) {
            nav = newNav;
        }
    }

    function updateOnboardingFeePercentage(uint256 newFeePercentage)
    public onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        require(newFeePercentage <= (100 * singleUnit));
        onboardingFeePercentage = newFeePercentage;
        success = true;
    }

    function updateWithdrawalFeePercentage(uint256 newFeePercentage)
    public onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        require(newFeePercentage <= (100 * singleUnit));
        withdrawalFeePercentage = newFeePercentage;
        success = true;
    }

    function updateOnboardingFeeCollector(address newFeeCollector)
    public onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        require(newFeeCollector != address(0));
        onboardingFeeCollector = newFeeCollector;
        success = true;
    }

    function updateWithdrawalFeeCollector(address newFeeCollector)
    public onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        require(newFeeCollector != address(0));
        withdrawalFeeCollector = newFeeCollector;
        success = true;
    }

    function updateCompetition(address newCompetition)
    public onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        require(newCompetition != address(0));
        competition = newCompetition;
        success = true;
    }

    function calculateFee(uint256 amount, uint256 feePercentage)
    internal view
    returns (uint256 fee)
    {
        fee = amount * feePercentage / singleUnit;
    }
}
