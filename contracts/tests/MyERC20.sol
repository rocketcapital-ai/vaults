// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;
import 'OpenZeppelin/openzeppelin-contracts@4.7.0/contracts/token/ERC20/presets/ERC20PresetFixedSupply.sol';

contract MyERC20 is ERC20PresetFixedSupply{
    constructor(
        string memory name,
        string memory symbol,
        uint256 initialSupply,
        address owner
    ) ERC20PresetFixedSupply(name, symbol, initialSupply, owner)
    {}

    function decimals()
    public view override
    returns (uint8)
    {
        return 6;
    }
}
