// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
import "../TransferFeeToken.sol";


contract TestERC20 is TransferFeeToken {
    constructor(
        string memory name_,
        string memory symbol_,
        address blacklistPolicy_,
        address admin_
    ) TransferFeeToken(name_, symbol_, blacklistPolicy_, admin_)
    {}

    function mint(address to, uint256 amount)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        _mint(to, amount);
    }

    function burn(uint256 amtToBurn)
    external onlyRole(RCI_CHILD_ADMIN)
    {
        _burn(address(this), amtToBurn);
    }

    function decimals()
    public view override
    returns (uint8)
    {
        return 6;
    }
}
