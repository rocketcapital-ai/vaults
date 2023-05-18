// SPDX-License-Identifier: MIT
pragma solidity ^0.8.15;

import "./RequestManager.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/proxy/Clones.sol";
import "./Types.sol";
import "./Router.sol";

contract Processor is PendingToken, Types {

    using Clones for address;
    RequestManager public withdrawRequestManager;
    address public vault;
    bytes32 public constant RCI_VAULT = keccak256('RCI_VAULT');

    constructor ()
    {
        _disableInitializers();
    }

    function setup (string memory name_, string memory symbol_,
        address requestManagerImpl, string memory parentSymbol_,
        address vault_, address admin_
    )
    external initializer
    {
        PendingToken.setup(name_, symbol_, admin_);
        vault = vault_;

        withdrawRequestManager = RequestManager(requestManagerImpl.clone());
        withdrawRequestManager.setup(
            string.concat("Pending withdraw for ", parentSymbol_),
            string.concat("pw-", parentSymbol_), vault_,
            vault_,
            admin_
        );

        _grantRole(RCI_VAULT, vault_);
        _setRoleAdmin(RCI_VAULT, RCI_MAIN_ADMIN);
    }

    function processSingleWithdrawal(uint256 pSharesIn, address receiver, uint256 nav, uint256 singleUnit)
    external onlyRole(RCI_VAULT)
    returns (uint256 pwUsdcOut)
    {
        require(pSharesIn > 0, "nothing to deposit");
        withdrawRequestManager.redeem(pSharesIn, address(this), receiver);
        pwUsdcOut = pSharesIn * nav / singleUnit;
        shareMint(receiver, pwUsdcOut);
    }

    function reclaimPwUsdc(uint256 pwUsdc, address user)
    external onlyRole(RCI_VAULT)
    {
        require(pwUsdc > 0);
        burnFrom(user, pwUsdc); // 1:1 pw-USDC to USDC ratio
    }

}