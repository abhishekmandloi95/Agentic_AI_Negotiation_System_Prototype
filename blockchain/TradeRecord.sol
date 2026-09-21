// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract TradeRecord {
    string public recordJson;
    bytes32 public recordHash;
    constructor(string memory payload) {
        recordJson = payload;
        recordHash = keccak256(bytes(payload));
    }
}
