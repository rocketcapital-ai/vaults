// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;
import "./TransferFeeToken.sol";

abstract contract ShareToken is TransferFeeToken {

    constructor(
        string memory name_,
        string memory symbol_,
        address blacklistPolicy_,
        address admin_
    ) TransferFeeToken(name_, symbol_, blacklistPolicy_, admin_) {}

    event SharesMinted(address indexed recipient, uint256 indexed amount);
    event SharesBurned(address indexed from, uint256 indexed amount);

    function shareMint(address to, uint256 amount) internal
    {
        _mint(to, amount);
    }

    function burnShares(uint256 amtToBurn)
    internal
    {
        _burn(address(this), amtToBurn);
    }

    function decimals()
    public view override
    returns (uint8) {
        return 6;
    }

}
