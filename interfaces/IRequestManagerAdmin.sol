// SPDX-License-Identifier: MIT
pragma solidity ^0.8.15;

interface IRequestManagerAdmin {
    
    // View methods

    /*
    @dev: function for getting the number of asset tokens sent to this contract without using any of the 
    @dev: methods for subscription.
    @return: amount of asset tokens this contract holds that are not part of the AUM.
    */
    function getRemainderAssetToken() external view returns (uint256 remainderAssetToken);

    // State-changing methods

    /*
    @dev: Send asset tokens that are under the fund contract's balance that do not belong to the AUM to the input address.
    @param: receiver: Address to send the tokens to.
    @return: true if completed successfully.
    */
    function refundRemainder(address receiver) external returns (bool success);

    /*
    @dev: Flip the status of 'subscriptionSuspended' from true to false, or false to true.
    @return: true if completed successfully.
    */
    function toggleSuspendSubscription() external returns (bool success);

    /*
    @dev: Flip the status of 'redemptionSuspended' from true to false, or false to true.
    @return: true if completed successfully.
    */
    function toggleSuspendRedemption() external returns (bool success);

    /*
    @dev: Update global maximum limits for deposit, mint, withdraw or redeem.
    @param: limitId: Id number to indicate which of the 4 max values to modify. See enum MaxId.
    @param: newLimit: New limit value to update to. Note that Deposit and Withdraw limit values should share the
    @param: same decimal places as the share token, while Mint and Redeem limit values should share the
    @param: same decimal places as the asset token.
    @return: true if completed successfully.
    */
    function updateGlobalMax(MaxId limitId, uint256 newLimit) external returns (bool success);

    /*
    @dev: Update global maximum limits for deposit, mint, withdraw or redeem.
    @param: limitId: Id number to indicate which of the 4 max values to modify. See enum MaxId.
    @param: userAddress: Address to apply this limit to.
    @param: newLimit: New limit value to update to. Note that Deposit and Withdraw limit values should share the
    @param: same decimal places as the share token, while Mint and Redeem limit values should share the
    @param: same decimal places as the asset token.
    @return: true if completed successfully.
    */
    function updateIndividualMax(MaxId limitId, address userAddress, uint256 newLimit) external returns (bool success);

    // Events
    event FeeUpdated(string feeName, uint256 indexed fxd, uint256 indexed pct, uint8 cyclicFeeId);
    event RemainderRefunded(address indexed recipient, uint256 remainderAssetAmount);
    event SubscriptionStatusChanged(bool indexed suspended);
    event RedemptionStatusChanged(bool indexed suspended);
    event GlobalLimitUpdated(string limitName, uint256 indexed oldLimit, uint256 indexed newLimit);
    event IndividualLimitUpdated(string limitName, address indexed userAddress, uint256 indexed oldLimit, uint256 indexed newLimit);


    // Enums

    enum MaxId { Deposit,  Mint,  Withdraw,  Redeem }

    //Structs

    /*
    @dev: fxd and pct should be specified with the same number of decimals as the fund's asset token.
    @dev: fxd should be specified in terms of the asset.
    @dev: For example, where the asset is USDC, the asset token has 6 decimals,
    @dev: and where the fee structure has a base fee of 1 USDC + 2% of the deposit amount, this should be
    @dev: fxd = 1 000 000, pct = 20 000
    @dev: fxd and pct are specified in asset token decimals.
    */
    struct Fee {
        uint128 fxd;
        uint128 pct;
    }
}
