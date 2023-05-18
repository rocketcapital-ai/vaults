// SPDX-License-Identifier: MIT

pragma solidity ^0.8.15;

import "../RequestManager.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/proxy/Clones.sol";

contract RequestManagerDeployer {
    mapping(uint256 => address) public deployedAddresses;
    uint256 public counter;

    using Clones for address;

    constructor(){}

    function deployRequestManager(
        address implAddress_,
        string memory name_, string memory symbol_, address aumTokenAddress_,
        address vault_, address admin_
    )
    external
    {
        RequestManager newRequestManager = RequestManager(implAddress_.clone());
        uint256 currentCounter = counter;
        deployedAddresses[currentCounter] = address(newRequestManager);
        newRequestManager.setup(
            name_, symbol_, aumTokenAddress_, vault_, admin_
        );
    }
}
