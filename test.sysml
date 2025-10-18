package LightSwitch {
  attribute mainsElectricityLevel = 10;
  item def FlipBus {
    attribute flipCmd;
  }

  part lightSwitch {
    port flipPort {
      in item flipBus defined by FlipBus {
        attribute flipCmd;
      }

    }

    attribute maxPowerLevel = 20;
    attribute powerLevel := 0;
    action def ClearPower {
      assign powerLevel := 0;
    }

    action def ActivatePower {
      assign powerLevel := 20;
    }

    state lightSwitchState {
      entry initial;
      state on {
        entry action activatePower defined by ActivatePower;
      }

      state off {
        entry action clearPower defined by ClearPower;
      }

      transition  first initial then off;
      transition offToOn first off if flipPort.flipBus.flipCmd then on;
      transition onToOff first on if flipPort.flipBus.flipCmd then off;
    }

  }

}
