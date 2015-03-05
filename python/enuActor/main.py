#!/usr/bin/env python

from Devices import shutter, bia, slit, temperature, enu, rexm
try:
    import actorcore.Actor
except Exception, e:
    print e

class OurActor(actorcore.Actor.Actor):
    def __init__(self, name, productName=None, configFile=None, debugLevel=30):
        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.Actor.Actor.__init__(self, name,
                                       productName=productName,
                                       configFile=configFile)
        self.shutter = shutter.Shutters(actor=self)
        self.slit = slit.Slit(actor=self)
        self.bia = bia.Bia(actor=self)
        self.rexm = rexm.Rexm(actor=self)
        self.temperature = temperature.Temperature(actor=self)
        self.enu = enu.Enu(actor=self)

#
# To work
def main():
    theActor = OurActor('enu', productName='enuActor')
    theActor.run()

if __name__ == '__main__':
    main()
