#!/usr/bin/env python3

import subprocess
import sys
from time import sleep

# Points in the curve: temperature ºC, fan speed %
curve = [(0, 0), (40, 0), (50, 40), (60, 75), (100, 100)]  # edit this list of points
sleepTime = 10

def getTargetFanSpeed(t):
    """
    Interpolates a fan speed given a temperature, and using the global curve
    :param t: temperature
    :return: the desired fan speed for that temperature
    """

    # Find the place where the temperature is in the curve. t will be between leftPoint and leftPoint + 1
    leftPoint = -1
    for i in range(len(curve)):
        if t >= curve[i][0]:
            leftPoint = i
        else:
            break

    # Points outside the curve use a flat extrapolation, just use the speed of the first or last point
    if leftPoint < 0:
        return curve[0][1]
    elif leftPoint >= len(curve) - 1:
        return curve[-1][1]
    else:
        # Between two points in the curve, the interpolation is linear
        t0 = curve[leftPoint][0]
        t1 = curve[leftPoint + 1][0]
        s0 = curve[leftPoint][1]
        s1 = curve[leftPoint + 1][1]
        if t0 == t1:
            return s1
        a = (s1 - s0) / (t1 - t0)
        b = (t1 * s0 - t0 * s1) / (t1 - t0)
        s = a * t + b
        return int(s)

def getCoreTemp():
    return getAttribute("gpu:0", "GPUCoreTemp")

def getCurrentFanSpeed():
    return getAttribute("fan:0", "GPUCurrentFanSpeed")

def getCurrentFanSpeedRPM():
    return getAttribute("fan:0", "GPUCurrentFanSpeedRPM")

def getAttribute(target, attribute):
    output = str(subprocess.check_output(["nvidia-settings", "-q=[" + target + "]/" + attribute],
                                         stderr=subprocess.DEVNULL,
                                         universal_newlines=True))

    positionStart = output.find(target) + len(target) + 4
    positionEnd = output.find(".", positionStart)
    integerAttribute = int(output[positionStart:positionEnd])
    return integerAttribute

def setTargetFanSpeed(speed):
    subprocess.call(["nvidia-settings", "-a",
                     "[fan:0]/GPUTargetFanSpeed=" + str(speed)],
                    stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

def enableCoolBits():
    output = setAttribute("gpu:0", "GPUFanControlState", 1)
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
    print(" Reset fan speed to auto mode")
    setAttribute("gpu:0", "GPUFanControlState", 0)

def setAttribute(target, attribute, value):
    return str(subprocess.check_output(["nvidia-settings", "-a", "[%s]/%s=%d" % (target, attribute, value)],
                            stderr=subprocess.DEVNULL, universal_newlines=True))

def getLineGraph(value, min, max, width, unit, direction):
    """
Build a row for a vertical graph
    :param value: Current value for this row
    :param min: Min allowed value in the graph.
    :param max: Max allowed value in the graph
    :param width: Width of the graph measured in console characters
    :param unit: String to be printed next to the value
    :param direction: 1, -1 or 0 to also print an arrow pointing to the right, left or no arrow at all
    :return: The row to be printed
    """
    if width <= 0:
        return ""
    elif max - min == 0:
        return ""

    rightArrow = "-> "
    leftArrow = "<- "
    dot = "."
    label = " %d%s %s" % (value, unit, rightArrow if direction == 1 else leftArrow if direction == -1 else "")

    a = width/(max - min)
    b = -width*min/(max - min)
    x = int(a*value + b)

    result = "|"
    result += dot * x
    result += label
    result += dot * (width - x - len(label))
    if len(result) <= (width + 1):
        result += "|"

    return result

def main():
    if len(curve) <= 0:
        print("User-defined curve is empty. Exit now")
        sys.exit(1)

    if not enableCoolBits():
        sys.exit(1)

    targetFanSpeedOld = getCurrentFanSpeed()
    while True:
        coreTemp = getCoreTemp()
        targetFanSpeed = getTargetFanSpeed(coreTemp)
        rpm = getCurrentFanSpeedRPM()
        info = "GPU temp is %dºC; fan spins at %4d RPM " % (coreTemp, rpm)
        direction = 0
        if targetFanSpeed != targetFanSpeedOld:
            if targetFanSpeed > targetFanSpeedOld:
                direction = 1
            else:
                direction = -1
            setTargetFanSpeed(targetFanSpeed)
            targetFanSpeedOld = targetFanSpeed

        info += " " + getLineGraph(targetFanSpeed, 0, 100, 50, "%", direction)
        print(info)
        sleep(sleepTime)

if __name__ == "__main__":
    try:
        main()
    finally:
        finish()
        sys.exit(0)
