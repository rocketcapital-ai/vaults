// SPDX-License-Identifier: MIT
pragma solidity ^0.8.15;

import "../../interfaces/IBlacklistPolicy.sol";
import "../AccessControlRci.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/token/ERC20/ERC20.sol";

contract BlacklistPolicyWhitelist is IBlacklistPolicy, AccessControlRci {

    mapping (address => bool) public isBlacklisted;
    mapping (address => bool) public isWhitelisted;

    constructor() {
        _initializeRciAdmin(msg.sender);
    }

    function updateBlacklist(address acct, bool toBlacklist)
    external onlyRole(RCI_CHILD_ADMIN)
    returns (bool)
    {
        isBlacklisted[acct] = toBlacklist;
        return true;
    }

    function updateWhitelist(address acct, bool toWhitelist)
    external onlyRole(RCI_CHILD_ADMIN)
    returns (bool)
    {
        isWhitelisted[acct] = toWhitelist;
        return true;
    }

    function _policy(address from, address to)
    internal view
    returns (bool)
    {
        return !(isBlacklisted[to] || isBlacklisted[from]);
    }

    function transferPolicy(address from, address to, uint256 amount)
    external view override
    returns (bool)
    {
        return (
        isWhitelisted[from] || isWhitelisted[to]
        || (from == address(0)) // for minting
        || (to == address(0)) // for burning
        );
    }

    function depositPolicy(uint256 assets, uint256 shares,address receiver, address sender)
    external view override
    returns (bool)
    {
        return _policy(receiver, sender);
    }

    function withdrawPolicy(uint256 assets, uint256 shares,address receiver, address sender)
    external view override
    returns (bool)
    {
        return _policy(receiver, sender);
    }
}
