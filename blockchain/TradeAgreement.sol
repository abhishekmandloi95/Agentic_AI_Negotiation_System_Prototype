// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract TradeAgreement {
    address public initiator;
    address public responder;
    string public serviceGiven;
    string public serviceReceived;
    uint public quantityGiven;
    uint public quantityReceived;

    constructor(
        address _initiator,
        address _responder,
        string memory _serviceGiven,
        string memory _serviceReceived,
        uint _quantityGiven,
        uint _quantityReceived
    ) {
        initiator = _initiator;
        responder = _responder;
        serviceGiven = _serviceGiven;
        serviceReceived = _serviceReceived;
        quantityGiven = _quantityGiven;
        quantityReceived = _quantityReceived;
    }
}