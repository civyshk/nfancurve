#!/usr/bin/env python3

import subprocess
import sys
from time import sleep

# Points in the curve: temperature ºC, fan speed %
curve = [(0, 0), (20, 0), (40, 40), (60, 75), (100, 100)]  # edit this list of points, don't use same temperature twice
sleepTime = 10

def getFanSpeed(t):
    temperaturePoints = [x for x, y in curve]
    leftPoint = -1
    for i in range(len(temperaturePoints)):
        if t >= temperaturePoints[i]:
            leftPoint = i
        else:
            break

    if leftPoint < 0:
        return curve[0][1]
    elif leftPoint >= len(temperaturePoints):
        return curve[-1][1]
    else:
        t0 = temperaturePoints[leftPoint]
        t1 = temperaturePoints[leftPoint + 1]
        s0 = curve[leftPoint][1]
        s1 = curve[leftPoint + 1][1]
        a = (s1 - s0) / (t1 - t0)
        b = (t1 * s0 - t0 * s1) / (t1 - t0)
        s = a * t + b
        return int(s)

def enableCoolBits():
    output = subprocess.check_output(["nvidia-settings", "-a", '[gpu:0]/GPUFanControlState=1'],
                                     stderr=subprocess.DEVNULL,
                                     universal_newlines=True)
    position0 = output.find("assigned value")
    positionStart = position0 + 15
    positionEnd = output[positionStart:].find(".") + positionStart
    value = 0
    try:
        value = int(output[positionStart:positionEnd])
    except Exception as e:
        print(e)
        pass

    if value == 1:
        return True
    else:
        print("Couldn't enable CoolBits. Output: " + output)
        return False

def finish():
    subprocess.check_output(["nvidia-settings", "-a", '[gpu:0]/GPUFanControlState=0'],
                            stderr=subprocess.DEVNULL, universal_newlines=True)

def main():
    if len(curve) <= 0:
        print("User-defined curve is empty. Exit now")
        sys.exit(1)

    if not enableCoolBits():
        sys.exit(1)

    while True:
        output = str(subprocess.check_output(["nvidia-settings", "-q=[gpu:0]/GPUCoreTemp"],
                                             stderr=subprocess.DEVNULL,
                                             universal_newlines=True))

        position0 = output.find("'GPUCoreTemp' is an integer attribute")
        positionStart = output[:position0].rfind(":") + 2
        positionEnd = output[positionStart:].find(".") + positionStart
        currentTemperature = int(output[positionStart:positionEnd])
        desiredFanSpeed = getFanSpeed(currentTemperature)
        print("GPU temperature is %dºC: set fan at %d%%"
              % (currentTemperature, desiredFanSpeed))
        subprocess.call(["nvidia-settings", "-a",
                         "[fan:0]/GPUTargetFanSpeed=" + str(desiredFanSpeed)],
                        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        sleep(sleepTime)

if __name__ == "__main__":
    try:
        main()
    finally:
        finish()
        sys.exit(0)
