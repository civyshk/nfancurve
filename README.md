# nvidiafancurve
A python script which allows you to control the fan curve of a Nvidia GPU in Linux

## Steps:
1. Open temperature.py with your favourite editor and edit the curve like this:
```python
    curve = [(0, 0), (40, 0), (50, 40), (60, 75), (100, 100)]
```
being the numbers in parenthesis pairs of (temperature ºC, fan speed %)
  
2. Save it and let it run: 
```bash
$ python3 temperature.py
```
## Example:
[![nvidiascreen.png](https://s23.postimg.org/ynt7mw5ej/nvidiascreen.png)](https://postimg.org/image/et760rq6v/)
