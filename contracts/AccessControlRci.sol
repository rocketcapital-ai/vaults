pragma solidity ^0.8.4;

// SPDX-License-Identifier: MIT

import 'OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/access/AccessControlEnumerable.sol';

abstract contract AccessControlRci is AccessControlEnumerable{
    bytes32 public constant RCI_MAIN_ADMIN = keccak256('RCI_MAIN_ADMIN');
    bytes32 public constant RCI_CHILD_ADMIN = keccak256('RCI_CHILD_ADMIN');

    function _initializeRciAdmin(address admin)
    internal
    {
        _grantRole(RCI_MAIN_ADMIN, admin);
        _setRoleAdmin(RCI_MAIN_ADMIN, RCI_MAIN_ADMIN);

        _grantRole(RCI_CHILD_ADMIN, admin);
        _setRoleAdmin(RCI_CHILD_ADMIN, RCI_MAIN_ADMIN);
    }

    function renounceRole(bytes32 role, address account) public override(IAccessControl, AccessControl) {
        // make method unavailable for public use.
        revert("Not permitted.");
    }
}
