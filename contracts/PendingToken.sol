// SPDX-License-Identifier: MIT
pragma solidity ^0.8.4;
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/token/ERC20/ERC20.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/utils/structs/EnumerableSet.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/token/ERC20/utils/SafeERC20.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/proxy/utils/Initializable.sol";
import "./AccessControlRci.sol";
import "./../interfaces/IShareTaxPolicy.sol";

abstract contract PendingToken is ERC20, AccessControlRci, Initializable {
    using EnumerableSet for EnumerableSet.AddressSet;
    EnumerableSet.AddressSet private shareHolders;
    bool private recursionFlag;
    string private _name;
    string private _symbol;

    using Address for address;

    constructor () ERC20("_", "_") {}

    function setup(string memory name_, string memory symbol_, address admin_)
    internal
    {
        _initializeRciAdmin(admin_);
        _name = name_;
        _symbol = symbol_;
    }

    function name() public view override returns (string memory) {
        return _name;
    }

    function symbol() public view override returns (string memory) {
        return _symbol;
    }

    function shareMint(address to, uint256 amount) internal
    {
        _mint(to, amount);
    }

    function _afterTokenTransfer(address from, address to, uint256 amount)
    internal override
    {
        updateShareHolders(from);
        updateShareHolders(to);
    }

    function transfer(address to, uint256 amount)
    public override
    returns (bool) {
        address owner = _msgSender();
        require(owner == address(this));
        _transfer(owner, to, amount);
        return true;
    }

    function transferFrom(
        address from,
        address to,
        uint256 amount
    )
    public override
    returns (bool) {
        revert(); // prevent use
    }

    function burnFrom(address account, uint256 amount)
    internal
    {
        _burn(account, amount);
    }

    function numberOfShareHolders()
    public view
    returns (uint256 holdersCount)
    {
        holdersCount = shareHolders.length();
    }

    function updateShareHolders(address userAddress)
    internal
    {
        if (balanceOf(userAddress) > 0) {
            shareHolders.add(userAddress);
        } else {
            shareHolders.remove(userAddress);
        }
    }

    function getShareHolders(uint256 startIndex, uint256 endIndex)
    external view
    returns (address[] memory shareHoldersList)
    {
        shareHoldersList = getListFromSet(shareHolders, startIndex, endIndex);
    }


    function getListFromSet(EnumerableSet.AddressSet storage setOfData, uint256 startIndex, uint256 endIndex)
    internal view
    returns (address[] memory listOfData)
    {
        listOfData = new address[](endIndex - startIndex);
        for (uint i = startIndex; i < endIndex; i++){
            listOfData[i - startIndex] = setOfData.at(i);
        }
    }

    function decimals()
    public view override
    returns (uint8) {
        return 6;
    }
}
