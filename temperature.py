#!/usr/bin/env python3

import subprocess
from time import sleep

def getFan(temperature):
    if temperature < 40:
        return 0
    elif temperature < 60:
        return temperature * 3 - 120  # 0%@40ºC, 60%@60ºC
    else:
        return min(temperature, 100)  # 60%@60ºC


if __name__ == "__main__":
    subprocess.call(["nvidia-settings", "-a", '[gpu:0]/GPUFanControlState=1'])  # TODO check output
    while True:
        output = str(subprocess.check_output(["nvidia-settings", "-q=[gpu:0]/GPUCoreTemp"],
                                             stderr=subprocess.DEVNULL,
                                             universal_newlines=True))
        position0 = output.find("'GPUCoreTemp' is an integer attribute")
        positionStart = output[:position0].rfind(":") + 2
        positionEnd = output[positionStart:].find(".") + positionStart
        currentTemperature = int(output[positionStart:positionEnd])
        desiredFanSpeed = getFan(currentTemperature)
        print("GPU temperature is %dºC: set fan at %d%%"
              % (currentTemperature, desiredFanSpeed))
        subprocess.call(["nvidia-settings", "-a",
                         "[fan:0]/GPUTargetFanSpeed="+str(desiredFanSpeed)],
                        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        sleep(10)
