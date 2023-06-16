// SPDX-License-Identifier: MIT
pragma solidity ^0.8.15;

import "./PendingToken.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/security/ReentrancyGuard.sol";
import "OpenZeppelin/openzeppelin-contracts@4.8.0/contracts/interfaces/IERC4626.sol";
import "../interfaces/IRequestManagerAdmin.sol";

contract RequestManager is ReentrancyGuard, PendingToken, IERC4626, IRequestManagerAdmin {

    // specified addresses
    IERC20Metadata public assetToken;
    using SafeERC20 for IERC20Metadata;

    // fund variables
    uint256 public singleUnit;
    uint256 public nav;
    address public vault;
    uint256 public cycleNumber;
    uint256 public totalDeposited;
    bool public subscriptionSuspended;
    bool public redemptionSuspended;

    // Limits
    mapping (address => uint256) public maxDepositMap;
    mapping (address => uint256) public maxMintMap;
    mapping (address => uint256) public maxWithdrawMap;
    mapping (address => uint256) public maxRedeemMap;
    uint256 public globalMaxDepositAmount;
    uint256 public globalMaxMintAmount;
    uint256 public globalMaxWithdrawAmount;
    uint256 public globalMaxRedeemAmount;
    uint256 public minimumDeposit;

    bytes32 public constant RCI_INFLOW_MGR = keccak256('RCI_INFLOW_MGR');
    bytes32 public constant RCI_OUTFLOW_MGR = keccak256('RCI_OUTFLOW_MGR');
    bytes32 public constant RCI_VAULT = keccak256('RCI_VAULT');

    constructor ()
    {
        _disableInitializers();
    }


    function setup(string memory name_, string memory symbol_, address aumTokenAddress_,
        address vault_, address admin_
    )
    public initializer

    {
        PendingToken.setup(name_, symbol_, admin_);
        require(aumTokenAddress_ != address(0), string.concat("aum token error", symbol_));
        assetToken = IERC20Metadata(aumTokenAddress_);
        singleUnit = 10 ** decimals();
        nav = singleUnit;
        vault = vault_;
        _grantRole(RCI_VAULT, vault_);
        _setRoleAdmin(RCI_INFLOW_MGR, RCI_VAULT);
        _setRoleAdmin(RCI_OUTFLOW_MGR, RCI_VAULT);
        globalMaxDepositAmount = 2 ** 256 - 1;
        globalMaxWithdrawAmount = 2 ** 256 - 1;
        globalMaxMintAmount = 2 ** 256 - 1;
        globalMaxRedeemAmount = 2 ** 256 - 1;
    }

    function asset()
    external view override
    returns(address assetTokenAddress)
    {
        assetTokenAddress = address(assetToken);
    }

    function totalAssets()
    public view override
    returns(uint256 totalManagedAssets)
    {
        totalManagedAssets = totalDeposited;
    }

    function convertToShares(uint256 assets)
    public view override
    returns (uint256 shares)
    {
        shares = assets;
    }

    function convertToAssets(uint256 shares)
    public view override
    returns (uint256 assets)
    {
        assets = shares;
    }

    function maxDeposit(address receiver)
    public view override
    returns (uint256 maxAssets)
    {
        if (subscriptionSuspended) {
         maxAssets = 0;
        } else {
            uint256 individualLimit = maxDepositMap[receiver];
            if (individualLimit == 0) {
                maxAssets = globalMaxDepositAmount;
            } else {
                maxAssets = individualLimit;
            }
        }
    }

    function previewDeposit(uint256 assets)
    public view override
    returns (uint256 shares)
    {
        require(assets > 0, "Cannot deposit 0.");
        require(assets >= minimumDeposit, "Cannot deposit below minimum.");
        shares = convertToShares(assets);
    }

    function deposit(uint256 assets, address receiver)
    public nonReentrant onlyRole(RCI_INFLOW_MGR)
    returns (uint256 shares)
    {
        // Calculate how many shares to mint.
        shares = previewDeposit(assets);

        // Check limits.
        require(assets <= maxDeposit(receiver));
        require(shares <= maxMint(receiver));

        // mint share tokens for subscriber
        shareMint(receiver, shares);

        // perform updates
        totalDeposited += assets;

        // Transfer in asset.
        assetToken.safeTransferFrom(msg.sender, address(this), assets);

        // Move to vault.
        assetToken.transfer(vault, assets);

        // emit Deposit event
        emit Deposit(msg.sender, receiver, assets, shares);
    }

    function maxMint(address receiver)
    public view override
    returns (uint256 maxShares)
    {
       if (subscriptionSuspended) {
         maxShares = 0;
        } else {
           uint256 individualLimit = maxMintMap[receiver];
            if (individualLimit == 0) {
                maxShares = globalMaxMintAmount;
            } else {
                maxShares = individualLimit;
            }
        }
    }

    function previewMint(uint256 shares)
    public view override
    returns (uint256 assets)
    {
        require(shares > 0, "Cannot mint 0.");
        assets = convertToAssets(shares);
    }

    function mint(uint256 shares, address receiver)
    public nonReentrant onlyRole(RCI_INFLOW_MGR)
    returns (uint256 assets)
    {
        // Calculate assets to deposit.
        assets = previewMint(shares);

        // Check limits.
        require(shares <= maxMint(receiver));
        require(assets <= maxDeposit(receiver));
        require(assets >= minimumDeposit, "Cannot deposit below 0.");

         // Mint tokens.
        shareMint(receiver, shares);

        // perform updates
        totalDeposited += assets;

        // Transfer in assets.
        assetToken.safeTransferFrom(msg.sender, address(this), assets);

        // emit Deposit event
        emit Deposit(msg.sender, receiver, assets, shares);
    }

    function maxWithdraw(address owner)
    public view override
    returns (uint256 maxAssets)
    {
        maxAssets = 0;
    }

    function previewWithdraw(uint256 assets)
    public view override
    returns (uint256 shares)
    {
        require(assets == 0);
        shares = convertToShares(assets);
    }

    function withdraw(uint256 assets, address receiver, address owner)
    public nonReentrant onlyRole(RCI_OUTFLOW_MGR)
    returns (uint256 shares)
    {
        // calculate shares to burn
        shares = previewWithdraw(assets);

        // check limits
        require(assets <= maxWithdraw(owner));
        require(shares <= maxRedeem(owner));

        // burn share tokens.
        burnFrom(owner, shares);

        // perform updates
        totalDeposited -= assets;

        // Return asset.
        assetToken.safeTransfer(receiver, assets);

        // emit Withdraw event
        emit Withdraw(msg.sender, receiver, owner, assets, shares);
    }

    function maxRedeem(address owner)
    public view override
    returns (uint256 maxShares)
    {
       if (redemptionSuspended) {
         maxShares = 0;
        } else {
           maxShares = balanceOf(owner);
           uint256 individualLimit = maxRedeemMap[owner];
            if (maxRedeemMap[owner] == 0) {
                if (maxShares > globalMaxRedeemAmount) {
                    maxShares = globalMaxRedeemAmount;
                }
            } else {
                if (maxShares > individualLimit){
                    maxShares = maxRedeemMap[owner];
                }
            }
        }
    }

    function previewRedeem(uint256 shares)
    public view override
    returns (uint256 assets)
    {
        assets = 0;
    }

    function redeem(uint256 shares, address receiver, address owner)
    public nonReentrant onlyRole(RCI_OUTFLOW_MGR)
    returns (uint256 assets)
    {
        // calculate assets to receive
        assets = previewRedeem(shares);

        //check limits
        require(shares <= maxRedeem(owner));
        require(assets <= maxWithdraw(owner));

        // burn share tokens
        burnFrom(owner, shares);

        // perform updates
        totalDeposited -= assets;

        // Return asset.
        assetToken.safeTransfer(receiver, assets);

        emit Withdraw(msg.sender, receiver, owner, assets, shares);
    }

    function toggleSuspendSubscription()
    external override onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        subscriptionSuspended = !subscriptionSuspended;
        success = true;

        emit SubscriptionStatusChanged(subscriptionSuspended);
    }

    function toggleSuspendRedemption()
    external override onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        redemptionSuspended = !redemptionSuspended;
        success = true;

        emit RedemptionStatusChanged(redemptionSuspended);
    }

    function updateGlobalMax(MaxId limitId, uint256 newLimit)
    external override onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        uint256 oldLimit;
        if (limitId == MaxId.Deposit) {
            oldLimit = globalMaxDepositAmount;
            globalMaxDepositAmount = newLimit;
            emit GlobalLimitUpdated("Deposit", oldLimit, newLimit);
        }
        else if (limitId == MaxId.Mint){
            oldLimit = globalMaxMintAmount;
            globalMaxMintAmount = newLimit;
            emit GlobalLimitUpdated("Mint", oldLimit, newLimit);
        }
        else if (limitId == MaxId.Withdraw){
            oldLimit = globalMaxWithdrawAmount;
            globalMaxWithdrawAmount = newLimit;
            emit GlobalLimitUpdated("Withdraw", oldLimit, newLimit);
        }
        else {
            oldLimit = globalMaxRedeemAmount;
            globalMaxRedeemAmount = newLimit;
            emit GlobalLimitUpdated("Redeem", oldLimit, newLimit);
        }

        success = true;
    }

    function updateIndividualMax(MaxId limitId, address userAddress, uint256 newLimit)
    external override onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        uint256 oldLimit;
        if (limitId == MaxId.Deposit) {
            oldLimit = maxDepositMap[userAddress];
            maxDepositMap[userAddress] = newLimit;
            emit IndividualLimitUpdated("Deposit", userAddress, oldLimit, newLimit);
        }
        else if (limitId == MaxId.Mint){
            oldLimit = maxMintMap[userAddress];
            maxMintMap[userAddress] = newLimit;
            emit IndividualLimitUpdated("Mint", userAddress, oldLimit, newLimit);
        }
        else if (limitId == MaxId.Withdraw){
            oldLimit = maxWithdrawMap[userAddress];
            maxWithdrawMap[userAddress] = newLimit;
            emit IndividualLimitUpdated("Withdraw", userAddress, oldLimit, newLimit);
        }
        else {
            oldLimit = maxRedeemMap[userAddress];
            maxRedeemMap[userAddress] = newLimit;
            emit IndividualLimitUpdated("Redeem", userAddress, oldLimit, newLimit);
        }
        success = true;
    }

    function updateMinimumDeposit(uint256 newMinimumDeposit)
    external onlyRole(RCI_CHILD_ADMIN)
    returns (bool success)
    {
        minimumDeposit = newMinimumDeposit;
        success = true;
    }
}