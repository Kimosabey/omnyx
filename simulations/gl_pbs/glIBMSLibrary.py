#!/usr/bin/python
from datetime import date, time, datetime, timedelta
def getstrTimeNow():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def printTrace(msg):
    print('TR: {} {}'.format(getstrTimeNow(), msg))