# NvidiaFanCurve
This python program allows you to control the fan speed of Nvidia GPUs in Linux
depending on their temperature. GPLv3.

## Steps:
**1.**
Make sure you have nvidia-settings installed and working

**2.**
Enable Coolbits in your xorg.conf. To do that, just go root and create a file
named something like 51-nvidia-coolbits.conf under /usr/share/X11/xorg.conf.d/
with the following content:
```
    Section "Device"
        Identifier     "Device0"
        Driver         "nvidia"
        VendorName     "NVIDIA Corporation"
        Option         "Coolbits" "4"
    EndSection
    
    #blank end line
```
The Identifier field could have a different name for you, Device0 works for me.

The number in Coolbits can be anything over 4, but the man page of nvidia-xconfig
says that
> "For fan control set it to 4.  WARNING: this may cause system damage and void warranties."

So you know. Let it be 4 and don't blame me if the card starts burning.

**3.**
Open temperature.py with your favourite editor and edit the curve like this:
```python
curve = [(0, 0), (40, 0), (50, 40), (60, 75), (100, 100)]
```
being the numbers in parenthesis multiple pairs of (temperature ºC, fan speed %)

**4.**
Save and run it:
```bash
$ python3 temperature.py
```

**5.**
It's probably desired that you configure your system to run this at every boot
## Unknown:
Does it work with multiple cards? It's ready to do so but I can't test it so
it should fail

## Screenshot:
[![nvidiascreen.png](https://raw.githubusercontent.com/civyshk/nvidiafancurve/master/nvidiafancurve-capture.png)](https://raw.githubusercontent.com/civyshk/nvidiafancurve/master/nvidiafancurve-capture.png)
---
(c) 2017-2018 civyshk