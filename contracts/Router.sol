//// SPDX-License-Identifier: MIT
pragma solidity ^0.8.15;

import "./AccessControlRci.sol";
import "./RequestManager.sol";
import "./Vault.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/utils/structs/EnumerableSet.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/security/ReentrancyGuard.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/token/ERC20/utils/SafeERC20.sol";

contract Router is ReentrancyGuard, AccessControlRci
{
    using EnumerableSet for EnumerableSet.AddressSet;
    using EnumerableSet for EnumerableSet.UintSet;
    using SafeERC20 for IERC20Metadata;
    using Address for address;

    enum RequestType { Deposit, Withdraw, RefundDeposit, RefundWithdraw, ManualMint }
    struct RequestRecord {
        address vault;
        RequestType requestType;
        address sender;
        address receiver;
        uint256 timestamp;
        uint256 amount;
    }

    struct ProcessedRecord {
        address vault;
        RequestType requestType;
        address receiver;
        uint256 timestamp;
        uint256 amountIn;
        uint256 amountOut;
        uint256 feesPaid;
    }

    EnumerableSet.AddressSet private authorizedVaults;

    mapping (address => RequestRecord[]) public requestRecords;
    mapping (address => ProcessedRecord[]) public processedRecords;
    IBlacklistPolicy public blacklistPolicy;

    event BlacklistPolicyUpdated(address indexed oldAddress, address indexed newAddress);

    constructor(address blacklistPolicy_)
    {
        _initializeRciAdmin(msg.sender);
        blacklistPolicy = IBlacklistPolicy(blacklistPolicy_);
    }

    function updateBlacklistPolicyAddress(address newBlacklistPolicy)
    public onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        require(newBlacklistPolicy.isContract(), "blacklist must be a contract.");
        emit BlacklistPolicyUpdated(address(blacklistPolicy), newBlacklistPolicy);
        blacklistPolicy = IBlacklistPolicy(newBlacklistPolicy);
        success = true;
    }

    function authorizeVault(address vault)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        require(vault.isContract(), "vault must be a contract.");
        authorizedVaults.add(vault);
        IERC20Metadata usdcToken = IERC20Metadata(Vault(vault).usdcToken());
        IERC20Metadata shareToken = IERC20Metadata(vault);
        usdcToken.safeApprove(address(Vault(vault).pendingDepositUsdc()), type(uint256).max);
        shareToken.safeApprove(address(Vault(vault).pendingWithdrawShare()), type(uint256).max);
    }

    function deauthorizeVault(address vault)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        require(authorizedVaults.contains(vault), "vault not authorized.");
        authorizedVaults.remove(vault);
        IERC20Metadata usdcToken = IERC20Metadata(Vault(vault).usdcToken());
        IERC20Metadata shareToken = IERC20Metadata(vault);
        usdcToken.safeApprove(address(Vault(vault).pendingDepositUsdc()), 0);
        shareToken.safeApprove(address(Vault(vault).pendingWithdrawShare()), 0);
    }

    function numberOfAuthorizedVaults()
    external view
    returns (uint256 number)
    {
        number = authorizedVaults.length();
    }

    function getAuthorizedVault(uint256 index)
    external view
    returns (address vaultAddress)
    {
        vaultAddress = authorizedVaults.at(index);
    }

    function _updateRequestRecord(address user, RequestRecord memory record)
    internal
    {
        requestRecords[user].push(record);
    }

    function updateExchangeRecord(
        address user, uint8 requestType, address receiver,
        uint256 amountIn, uint256 amountOut, uint256 feesPaid
    )
    external
    {
        require(authorizedVaults.contains(msg.sender), "Vault not authorized.");
        ProcessedRecord memory record = ProcessedRecord({
            vault: msg.sender,
            requestType: RequestType(requestType),
            receiver: receiver,
            timestamp: block.timestamp,
            amountIn: amountIn,
            amountOut: amountOut,
            feesPaid: feesPaid
        });
        processedRecords[user].push(record);
    }

    function numberOfRecords(address user)
    external view
    returns (uint256, uint256)
    {
        return (requestRecords[user].length, processedRecords[user].length);
    }

    function getRecords(
        address user, uint256 requestStartIndex, uint256 requestEndIndex,
        uint256 processedStartIndex, uint256 processedEndIndex
    )
    external view
    returns (RequestRecord[] memory requests, ProcessedRecord[] memory processed)
    {
        requests = new RequestRecord[](requestEndIndex - requestStartIndex);
        for (uint i = requestStartIndex; i < requestEndIndex; i++){
            requests[i - requestStartIndex] = requestRecords[user][i];
        }

        processed = new ProcessedRecord[](processedEndIndex - processedStartIndex);
        for (uint i = processedStartIndex; i < processedEndIndex; i++){
            processed[i - processedStartIndex] = processedRecords[user][i];
        }
    }


    function depositRequest(address vault, uint256 amountUsdc, address receiver)
    external nonReentrant
    {
        require(authorizedVaults.contains(vault));
        require(blacklistPolicy.depositPolicy(amountUsdc, 0, receiver, msg.sender), "Failed blacklist check.");

        // Transfer in asset.
        IERC20Metadata usdcToken = IERC20Metadata(Vault(vault).usdcToken());
        usdcToken.safeTransferFrom(msg.sender, address(this), amountUsdc);

        Vault(vault).pendingDepositUsdc().deposit(amountUsdc, receiver);
        RequestRecord memory record = RequestRecord({
            vault: vault,
            requestType: RequestType.Deposit,
            sender: msg.sender,
            receiver: receiver,
            timestamp: block.timestamp,
            amount: amountUsdc
        });
        _updateRequestRecord(msg.sender, record);
        if (msg.sender != receiver) {
            _updateRequestRecord(receiver, record);
        }
    }

    function withdrawRequest(address vault, uint256 amountShares, address receiver)
    external nonReentrant
    {
        require(authorizedVaults.contains(vault));
        require(blacklistPolicy.withdrawPolicy(0, amountShares, receiver, msg.sender));

        // Transfer in shares.
        IERC20Metadata shareToken = IERC20Metadata(vault);
        shareToken.safeTransferFrom(msg.sender, address(this), amountShares);

        Vault(vault).pendingWithdrawShare().deposit(amountShares, receiver);
        RequestRecord memory record = RequestRecord({
            vault: vault,
            requestType: RequestType.Withdraw,
            sender: msg.sender,
            receiver: receiver,
            timestamp: block.timestamp,
            amount: amountShares
        });
        _updateRequestRecord(msg.sender, record);
        if (msg.sender != receiver) {
            _updateRequestRecord(receiver, record);
        }
    }
}