// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Audit record of an off-chain simulated agreement.
/// @dev Does not settle assets or authenticate participants' wallet signatures.
contract TradeRecord {
    string public recordJson;
    bytes32 public recordHash;
    constructor(string memory payload) {
        recordJson = payload;
        recordHash = keccak256(bytes(payload));
    }
}
