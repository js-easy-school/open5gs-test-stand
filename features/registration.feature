Feature: 5G subscriber registration
  The mobile core must admit provisioned subscribers and reject invalid identities.

  @positive
  Scenario: Provisioned subscriber registers and receives a PDU session
    Given subscriber "999700000000001" exists in Open5GS
    When the provisioned UE requests registration
    Then the UE reaches state "RM-REGISTERED"
    And an "internet" PDU session is active

  @negative
  Scenario: Unknown subscriber is rejected
    Given subscriber "999700000009999" is absent from Open5GS
    When a temporary UE requests registration with "ue-unknown.yaml"
    Then the AMF rejects IMSI "999700000009999"

  @negative
  Scenario: Subscriber with a wrong SIM key fails authentication
    Given subscriber "999700000000002" exists in Open5GS
    When a temporary UE requests registration with "ue-badkey.yaml"
    Then authentication fails for IMSI "999700000000002"
