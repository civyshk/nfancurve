#!/usr/bin/env python3

import subprocess
import sys
from time import sleep

class GPU:
    def __init__(self, index, gpuCoreName, gpuDescription):
        self.index = index
        self.gpuCoreName = gpuCoreName
        self.gpuCommandName = gpuCoreName.split("[")[1][:-1]
        self.gpuDescription = gpuDescription
        self.fanCoreName = None
        self.fanCommandName = None
        self.fanDescription = None
        self.isOK = False

    def setFanData(self, fanCoreName, fanDescription):
        self.fanCoreName = fanCoreName
        self.fanCommandName = fanCoreName.split("[")[1][:-1]
        self.fanDescription = fanDescription
        self.isOK = True

    def isOK(self):
        return self.isOK


class Curve:
    def __init__(self, dataPoints):
        # Points in the curve: temperature ºC, fan speed %
        self.dataPoints = None
        self.curveParamA = None
        self.curveParamB = None
        self.buildCurve(dataPoints)

    def safeSpeed(self, s):
        return min(max(s, 0), 100)

    def buildCurve(self, dataPoints):
        if len(dataPoints) <= 0:
            print("Error: User-defined curve is empty. Exit now")
            sys.exit(1)
            # TODO use some default curve?

        self.dataPoints = [(t, self.safeSpeed(s)) for t, s in dataPoints]
        self.curveParamA = []
        self.curveParamB = []
        # Between two points in the curve, the interpolation is linear
        # Cache the linear params here for later use
        for i in range(len(self.dataPoints) - 1):
            t0 = self.dataPoints[i][0]
            t1 = self.dataPoints[i + 1][0]
            s0 = self.dataPoints[i][1]
            s1 = self.dataPoints[i + 1][1]
            if t0 == t1:
                print("Warning: There are two speeds defined for the same temperature (%d ºC)" % t0)
                print("Not critical but check your curve points\n")
                self.curveParamA.append(None)
                self.curveParamB.append(None)
            else:
                self.curveParamA.append((s1 - s0) / (t1 - t0))
                self.curveParamB.append((t1 * s0 - t0 * s1) / (t1 - t0))

    def getTargetFanSpeed(self, temperature):
        """
        Interpolates a fan speed given a temperature, and using the global curve
        :param temperature: temperature
        :return: the desired fan speed for that temperature
        """

        # Find the place where the temperature is in the curve. t will be between leftPoint and leftPoint + 1
        leftPoint = -1
        for i in range(len(self.dataPoints)):
            if temperature >= self.dataPoints[i][0]:
                leftPoint = i
            else:
                break

        # Points outside the curve use a flat extrapolation, just use the speed of the first or last point
        if leftPoint < 0:
            return self.dataPoints[0][1]
        elif leftPoint >= len(self.dataPoints) - 1:
            return self.dataPoints[-1][1]

        # Use linear interpolation between points in the curve
        if self.curveParamA[leftPoint] is not None:
            return int(self.curveParamA[leftPoint] * temperature + self.curveParamB[leftPoint])

        # Unless the curve at that point is a vertical line
        else:
            return self.dataPoints[leftPoint + 1][1]


class NvidiaManager:
    def __init__(self, curve):
        self.curve = curve

        self.dopingEnabled = True
        self.dopingSpeed = 10
        self.maxSleepTime = 10  # s
        self.warningTemperatureChange = 1  # ºC/s
        self.minVersion = 304
        self.previousSleepTime = 1

        if self.getVersion() < self.minVersion:
            print("Error: Your Nvidia drivers are probably outdated, use at least version %d. Exit now" % self.minVersion)
            print("(If you want to test this script with your drivers, edit this .py script")
            print("and remove this check. If it works then, throw an email to civyshk@gmail.com)")
            sys.exit(1)

        self.gpus = self.getGPUs()
        self.updateFans(self.gpus)
        self.previousCoreTemps = {gpu: 30 for gpu in self.gpus}
        self.previousTargetFanSpeeds = {gpu: self.getCurrentFanSpeed(gpu) for gpu in self.gpus}
        self.initialFanControlEnabled = {gpu: self.isFanControlEnabled(gpu) for gpu in self.gpus}

    def getSleepTime(self, previousTemp, currentTemp, previousSleepTime):
        """
        The faster the temperature changes, the shorter is the sleep time
        I'm using the negative parabola 'sleep = a + b * v^2' ,
        being b negative
        being v = ΔT/previousSleepTime
        being ΔT = abs(currentTemp - previousTemp)
        being sleep = maxSleepTime when v == 0
        and   sleep = 1            when v = warningTemperatureChange
        :param previousTemp: Previous temperature
        :param currentTemp: Current temperature
        :param previousSleepTime: Previous sleep time
        :return: the recommended sleep time
        """

        temperatureChange = abs(previousTemp - currentTemp)/max(previousSleepTime, 1)
        if temperatureChange >= self.warningTemperatureChange:
            return 1

        a = self.maxSleepTime
        b = (1 - self.maxSleepTime) / self.warningTemperatureChange
        return max(a + b * temperatureChange ** 2, 1)  # Don't let the parabola fall below one second

    def getVersion(self):
        output = str(
            subprocess.check_output(["nvidia-settings", "-v"], stderr=subprocess.DEVNULL, universal_newlines=True))
        positionStart = output.find("version") + len("version ")
        positionEnd = output[positionStart:].find(".") + positionStart
        version = int(output[positionStart:positionEnd])
        return version

    def getGPUs(self):
        output = str(subprocess.check_output(["nvidia-settings", "-q", "gpus"],
                                             stderr=subprocess.DEVNULL,
                                             universal_newlines=True))
        lines = output.splitlines()
        numberGpus = int(lines[1][0:lines[1].find("GPU") - 1])
        gpus = []
        i = 0
        for line in lines[2:]:
            positionIndex = line.find("[" + str(i) + "]")
            # # Unused
            # positionFriendlyName = line.find("Has the following name")
            if positionIndex >= 0:
                positionOne = line.find(" ", positionIndex)  # [0] LSD:0[gpu:0] (GeForce foo)
                positionTwo = line.find(" ", positionOne + 1)  # 0  1            2             length

                gpuIndex = int(line[positionIndex + 1: positionOne - 1])
                assert (gpuIndex == i)
                gpuCoreName = line[positionOne + 1: positionTwo]
                gpuDescription = line[positionTwo + 2: len(line) - 2]

                gpus.append(GPU(gpuIndex, gpuCoreName, gpuDescription))
                i += 1

        assert (i == numberGpus)
        assert (i == len(gpus))
        return gpus

    def updateFans(self, gpus):
        output = str(subprocess.check_output(["nvidia-settings", "-q", "fans"],
                                             stderr=subprocess.DEVNULL,
                                             universal_newlines=True))
        lines = output.splitlines()
        numberFans = int(lines[1][0:lines[1].find("Fan") - 1])
        i = 0
        for line in lines[2:]:
            positionIndex = line.find("[" + str(i) + "]")
            # # Unused
            # positionFriendlyName = line.find("Has the following name")
            if positionIndex >= 0:
                positionOne = line.find(" ", positionIndex)  # [0] LSD:0[fan:0] (Fan 0)
                positionTwo = line.find(" ", positionOne + 1)  # 0  1            2       length

                fanIndex = int(line[positionIndex + 1: positionOne - 1])
                assert (fanIndex == i)
                fanCoreName = line[positionOne + 1: positionTwo]
                fanDescription = line[positionTwo + 2: len(line) - 2]

                assert (gpus[i].index == i)  # If not, I should manually look for the right gpu item
                gpus[i].setFanData(fanCoreName, fanDescription)
                i += 1

        assert (numberFans == i)
        assert (numberFans == len(gpus))

    def getAttribute(self, target, attribute):
        """
        Return the value of some attribute for a gpu or a fan
        :param target: the gpu of the fan to be queried
        :param attribute: the nvidia name of the attribute
        :return: an integer value of the attribute
        """
        output = str(subprocess.check_output(["nvidia-settings", "-q=[" + str(target) + "]/" + attribute],
                                             stderr=subprocess.DEVNULL, universal_newlines=True))

        positionStart = output.find(target) + len(target) + 4
        positionEnd = output.find(".", positionStart)
        return int(output[positionStart:positionEnd])

    def setAttribute(self, target, attribute, value):
        return str(subprocess.check_output(["nvidia-settings", "-a", "[%s]/%s=%d" % (target, attribute, value)],
                                           stderr=subprocess.DEVNULL, universal_newlines=True))

    def isFanControlEnabled(self, gpu):
        return self.getAttribute(gpu.gpuCommandName, "GPUFanControlState") == 1
        # TODO test. Check if enabling fan control in one GPU affects the state of the others
        # I can't test this

    def restoreInitialFanControlAll(self):
        for gpu in self.gpus:
            self.restoreInitialFanControl(gpu)

    def restoreInitialFanControl(self, gpu):
        if not self.initialFanControlEnabled[gpu]:
            self.disableFanControl(gpu)
        else:
            print(gpu.gpuCoreName + " doesn't set fan speed to auto mode, manual fan control was enabled before")

    def enableFanControlAll(self):
        for gpu in self.gpus:
            self.enableFanControl(gpu)

    def enableFanControl(self, gpu):
        output = self.setAttribute(gpu.gpuCommandName, "GPUFanControlState", 1)
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
            print(gpu.gpuCoreName + " couldn't enable FanControl. Output: " + output)
            print("Is Coolbits option enabled in /etc/X11/xorg.conf?")
            return False

    def disableFanControl(self, gpu):
        print(gpu.gpuCoreName + " resets fan speed to auto mode")
        self.setAttribute(gpu.gpuCommandName, "GPUFanControlState", 0)

    def getCurrentFanSpeed(self, gpu):
        return self.getAttribute(gpu.fanCommandName, "GPUCurrentFanSpeed")

    def getCoreTemp(self, gpu):
        return self.getAttribute(gpu.gpuCommandName, "GPUCoreTemp")

    def getCurrentFanSpeedRPM(self, gpu):
        return self.getAttribute(gpu.fanCommandName, "GPUCurrentFanSpeedRPM")

    # def everythingOK(self):
    #     return all(gpu.enableFanControl() for gpu in self.gpus)

    def setTargetFanSpeed(self, gpu, speed):
        self.setAttribute(gpu.fanCommandName, "GPUTargetFanSpeed", speed)

    def updateFanSpeed(self, gpu):
        coreTemp = self.getCoreTemp(gpu)
        targetFanSpeed = self.curve.getTargetFanSpeed(coreTemp)
        if self.dopingEnabled and coreTemp > self.previousCoreTemps[gpu] + self.warningTemperatureChange:
            targetFanSpeed = self.curve.safeSpeed(targetFanSpeed + self.dopingSpeed)

        sleepTime = self.getSleepTime(self.previousCoreTemps[gpu], coreTemp, self.previousSleepTime)
        self.previousCoreTemps[gpu] = coreTemp
        rpm = self.getCurrentFanSpeedRPM(gpu)
        # TODO fix this info for multi gpu
        # info = "GPU temp is %dºC; fan spins at %4d RPM. Sleep %2ds " % (coreTemp, rpm, round(sleepTime))
        direction = 0
        if targetFanSpeed != self.previousTargetFanSpeeds[gpu]:
            if targetFanSpeed > self.previousTargetFanSpeeds[gpu]:
                direction = 1
            else:
                direction = -1
            self.setTargetFanSpeed(gpu, targetFanSpeed)
            self.previousTargetFanSpeeds[gpu] = targetFanSpeed

        # TODO fix graph to show something acceptable
        # info += " " + getLineGraph(targetFanSpeed, 0, 100, 50, "%", direction)
        # print(info)
        print("Set speed to %d (%dºC) and sleep %d s" % (targetFanSpeed, coreTemp, sleepTime))
        return sleepTime

    def loop(self):
        while True:
            sleepTime = self.maxSleepTime
            for gpu in self.gpus:
                gpuSleepTime = self.updateFanSpeed(gpu)
                sleepTime = min(sleepTime, gpuSleepTime)

            self.previousSleepTime = sleepTime
            sleep(sleepTime)

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

class ConsoleGraph:
    def __init__(self, width, numberItems):
        self.width = max(10, width)
        self.numberItems = max(0, numberItems)
        self.itemWidth = self.width // self.numberItems - 1
        self.items = []
        self.startPositions = []
        self.endPositions = []

    def addItem(self, title, graphData, *extraData):
        self.items.append(GraphItem(title, self.itemWidth, 0, 100, graphData, extraData))  # TODO check 0 and 100

    def init(self):
        assert len(self.items) == self.numberItems
        for i in range(self.numberItems):
            self.startPositions.append((self.itemWidth + 1)*i)
            self.endPositions.append(self.itemWidth - 1 + (self.itemWidth + 1)*i)

    def updateData(self, itemIndex, graph, *extra):
        self.items[itemIndex].updateData(graph, extra)


class GraphItem:
    def __init__(self, title, graphWidth, minValue, maxValue, graphData, *extraData):
        """
        :param title: Title of item as a string
        :param graphWidth: How long is the graph line for this item, measured in characters, including those at start and end
        :param minValue: min value allowed in the graph
        :param maxValue: max ...
        :param graphData: Tuple containing (width of field, unit as a string) of data inside graph
        :param extraData: More tuples containing (width of field, unit as a string) of data outside graph
        """

        self.title = title
        self.graphTextWidth = graphData[0]
        self.graphUnit = graphData[1]
        self.graphWidth = max(2 + self.graphTextWidth + len(self.graphUnit), graphWidth)
        self.minValue = minValue
        self.maxValue = maxValue
        self.extraTextWidths = [x for x, y in extraData]
        self.extraUnits = [y for x, y in extraData]
        self.totalWidth = self.graphWidth + len(self.extraUnits) + \
                          sum(len(x) for x in self.extraUnits) + sum(x for x in self.extraTextWidths)

        self.previousGraphValue = self.minValue
        self.graphValue = self.minValue
        self.extraValues = [0] * len(self.extraUnits)

    def getTotalWidth(self):
        return self.totalWidth

    def updateData(self, graphValue, *extraValues):
        self.previousGraphValue = self.graphValue
        self.graphValue = graphValue
        self.extraValues = list(extraValues)

    def getGraph(self):
        pass
        #TODO. Reuse code somewhere above


if __name__ == "__main__":
    manager = None
    try:
        curve = Curve([(0, 0), (40, 30), (50, 60), (60, 75), (100, 100)])
        curve = Curve([(0, 0), (40, 30), (50, 60), (60, 75), (100, 100)])
        manager = NvidiaManager(curve)
        manager.enableFanControlAll()
        manager.loop()
    except Exception as e:
        print(e)
    finally:
        print("")
        manager.restoreInitialFanControlAll()
        sys.exit(0)
