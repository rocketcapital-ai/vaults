// SPDX-License-Identifier: MIT
pragma solidity ^0.8.15;

import "../../interfaces/IBlacklistPolicy.sol";
import "../AccessControlRci.sol";
import "./BlacklistOracle.sol";

contract BlacklistPolicyExternal is IBlacklistPolicy, AccessControlRci {

    constructor()
    {
        _initializeRciAdmin(msg.sender);
    }

    BlacklistOracle public oracleAddress;

    function updateBlacklistOracle(address newOracleAddress)
    external onlyRole(RCI_CHILD_ADMIN)
    returns (bool)
    {
        oracleAddress = BlacklistOracle(newOracleAddress);
        return true;
    }

    function _policy(address from, address to, uint256 amount)
    internal view
    returns (bool)
    {
        if (oracleAddress.isBlacklisted(to) || oracleAddress.isBlacklisted(from)) {
                return false;
        }
        return true;
    }

    function transferPolicy(address from, address to, uint256 amount)
    external view override
    returns (bool)
    {
        return _policy(from, to, amount);
    }

    function depositPolicy(uint256 assets, uint256 shares, address receiver, address sender)
    external view override
    returns (bool)
    {
        return _policy(receiver, sender, assets);
    }

    function withdrawPolicy(uint256 assets, uint256 shares, address receiver, address sender)
    external view override
    returns (bool)
    {
        return _policy(receiver, sender, assets);
    }
}
