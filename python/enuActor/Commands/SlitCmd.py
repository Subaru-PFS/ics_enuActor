#!/usr/bin/env python

import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
import sys
from enuActor.Devices.Error import CommErr, DeviceErr
from enuActor.MyFSM import FysomError


class SlitCmd(object):

    def __init__(self, actor):
        self.actor = actor
        self.vocab = [
            ('slit', 'status', self.status),
            ('slit', '<cmd>', self.command),
            ('slit', 'start [@(operation|simulation)]', self.set_mode),
            ('slit', 'GetHome', self.getHome),
            ('slit', 'GoHome', self.goHome),
            ('slit', 'SetHome <X> <Y> <Z> <U> <V> <W>',
                self.setHome),
            ('slit', 'SetHome CURRENT', self.setHomeCurrent),
            ('slit', 'MoveTo absolute <X> <Y> <Z> <U> <V> <W>',
                self.moveTo),
            ('slit', 'MoveTo relative [<X>] [<Y>] [<Z>] [<U>] [<V>] [<W>]',
                self.moveTo),
            ('slit', 'SetDither <X> <Y> <Z>', self.setDither),
            ('slit', 'dither axis', self.getDither),
            ('slit', 'SetFocus <X> <Y> <Z>', self.setFocus),
            ('slit', 'focus axis', self.getFocus),
            ('slit', 'dither', self.goDither),
            ('slit', '<dither>', self.goDither),
            ('slit', '<magnification>', self.setMagnification),
            ('slit', 'magnification', self.getMagnification),
            ('slit', 'focus', self.goFocus),
            ('slit', '<focus>', self.goFocus),
            ('slit', '@(off|load|busy|idle|fail)',
                self.set_state),
            ('slit', 'init', self.init),
            ('slit', 'halt', self.halt)
            ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("slit_slit", (1, 1),
                #keys.Key("test", types.Coordinate(), help=""),
                keys.Key("cmd", types.Float(), help="Command ascii"),
                keys.Key("X", types.Float(), help="X coordinate"),
                keys.Key("Y", types.Float(), help="Y coordinate"),
                keys.Key("Z", types.Float(), help="Z coordinate"),
                keys.Key("U", types.Float(), help="U coordinate"),
                keys.Key("V", types.Float(), help="V coordinate"),
                keys.Key("W", types.Float(), help="W coordinate"),
                keys.Key("dither", types.Float(),
                    help="Number of pixel along dither axis"),
                keys.Key("focus", types.Float(),
                    help="Number of pixel along focus axis"),
                keys.Key("magnification", types.Float(),
                    help="magnification value"),
                                        )


    def init(self, cmd):
        self.actor.slit.initialise()

    def halt(self, cmd):
        if self.actor.slit.fsm.current == "IDLE":
            self.actor.slit.safeOff()
        elif self.actor.slit.fsm.current == "LOADED":
            self.actor.slit.shutdown()
        else:
            self.actor.slit.warn("It's impossible to halt system from current state: %s"\
                    % self.actor.slit.current)

    def status(self, cmd):
        try:
            status = self.actor.slit.getStatus()
            self.actor.slit.finish('status = %s' % status)
        except AttributeError as e:
            cmd.error("text='slit did not start well. details: %s" % e)
        except:
            cmd.error("text='Unexpected error: %s'" % sys.exc_info()[0])

    def command(self, cmd):
        """Opens a terminal to communicate directly with device"""
        self.actor.slit.send("%s\r\n" %
        cmd.cmd.keywords["cmd"].values[0])

    def set_mode(self, cmd):
        name = cmd.cmd.keywords[-1].name
        if name.lower() in ['start','operation']:
            mode = 'operation'
        elif name.lower() == 'simulation':
            mode = 'simulated'
        else:
            cmd.error("text='unknow operation %s'" % name)

        try:
            self.actor.slit.change_mode(mode)
        except CommErr as e:
            self.actor.slit.error("text='%s'" % e)
        except:
            cmd.error("text='Unexpected error: [%s] %s'" % (
                    sys.exc_info()[0],
                    sys.exc_info()[1]))
        else:
            self.actor.shutter.finish('started/restarted well!')

    def set_state(self, cmd):
        state = cmd.cmd.keywords[0].name
        try:
            getattr(self.actor.slit.fsm, state)()
        except AttributeError as e:
            cmd.error("text='slit did not start well. details: %s" % e)
        except FysomError as e:
            cmd.error("text= Can't go to this state: %s -x-> %s'" %
            (self.actor.slit.fsm.current, state.upper()))

    def getHome(self, cmd):
        try:
            homePosition = self.actor.slit.getHome()
            self.actor.slit.finish("Home position : %s" % homePosition)
        except Exception, e:
            cmd.error("text= %s" % e)

    def setHome(self, cmd):
        X = cmd.cmd.keywords["X"].values[0]
        Y = cmd.cmd.keywords["Y"].values[0]
        Z = cmd.cmd.keywords["Z"].values[0]
        U = cmd.cmd.keywords["U"].values[0]
        V = cmd.cmd.keywords["V"].values[0]
        W = cmd.cmd.keywords["W"].values[0]
        try:
            self.actor.slit.setHome(posCoord =
                    map(float, [X, Y, Z, U, V, W]))
        except Exception, e:
            cmd.error("text= '%s'" % e)
        else:
            cmd.inform("setHome done successfully !")

    def setHomeCurrent(self, cmd):
        try:
            self.actor.slit.setHome()
        except Exception, e:
            cmd.error("text= '%s'" % e)
        else:
            cmd.inform("text= 'setHome done successfully !!'")

    def moveTo(self, cmd):
        reference = None
        pipe = cmd.cmd.keywords
        # we want to map to a list [x,y,z,...]
        positionMap = { 'X': 1, 'Y': 2, 'Z': 3, 'U': 4, 'V': 5, 'W': 6}
        position = dict(X=0.0, Y=0.0, Z=0.0, U=0.0, V=0.0, W=0.0)
        while len(pipe) > 0:
            item = pipe.pop()
            if item.name.lower() not in ["relative", "absolute", "moveto"]:
                position[item.name] = float(item.values[0])
            elif item.name in ["relative", "absolute"]:
                reference = item.name
        if reference is None:
            cmd.error('text="Error syntax "absolute or relative" \
expected and we have: %s"' % item.name)

        liste_position = [position[i] \
                          for i in sorted(position, key=positionMap.__getitem__)]

        try:
            self.actor.slit.moveTo(
                reference,
                posCoord=map(float, liste_position)
            )
        except Exception, e:
            cmd.error("text= '%s'" % e)
        else:
            cmd.inform("text= 'moveTo done successfully !!'")
        cmd.finish()

    def goHome(self, cmd):
        try:
            self.actor.slit.moveTo('absolute')
        except Exception, e:
            cmd.error("text= '%s'" % e)
        else:
            cmd.inform("text= 'goHome done successfully !!'")

    def setDither(self, cmd):
        try:
            self.actor.slit.dither_axis = map(
                    float,
                    [
                        cmd.cmd.keywords["X"].values[0],
                        cmd.cmd.keywords["Y"].values[0],
                        cmd.cmd.keywords["Z"].values[0]
                    ])
        except Exception, e:
            cmd.error("text='%s'" % e)
        else:
            cmd.inform("text= 'set dither done!'")

    def getDither(self, cmd):
        try:
            cmd.inform("text=='%s'" % self.actor.slit.dither_axis)
        except Exception, e:
            cmd.error("text='%s'" % e)

    def setFocus(self, cmd):
        try:
            self.actor.slit.focus_axis = map(
                    float,
                    [
                        cmd.cmd.keywords["X"].values[0],
                        cmd.cmd.keywords["Y"].values[0],
                        cmd.cmd.keywords["Z"].values[0]
                    ])
        except Exception, e:
            cmd.error("text='%s'" % e)
        else:
            cmd.inform("text= 'set focus done!'")

    def getFocus(self, cmd):
        try:
            cmd.inform("text='%s'" % self.actor.slit.focus_axis)
        except Exception, e:
            cmd.error("text='%s'" % e)

    def setMagnification(self, cmd):
        try:
            self.actor.slit.magnification =\
                    cmd.cmd.keywords["magnification"].values[0]
        except Exception, e:
            cmd.error("text='%s'" % e)
        else:
            cmd.inform("text= 'set magnification done!'")

    def getMagnification(self, cmd):
        try:
            cmd.inform("text='Magnification = %s'" %
                    self.actor.slit.magnification)
        except Exception, e:
            cmd.error("text='%s'" % e)

    def goDither(self, cmd):
        if cmd.cmd.keywords["dither"].values == []:
            #dithering undefined value
            length = self.actor.slit.dithering_value
        else:
            #dithering with defined value
            length = cmd.cmd.keywords["dither"].values[0]
        try:
            self.actor.slit.dither(length)
        except DeviceErr, e:
            cmd.error("text= '%s'" % e)
        except CommErr, e:
            cmd.error("text= '%s'" % e)
        except Exception, e:
            cmd.error("text= Unexpected error: '%s'" % e)
        else:
            cmd.inform("text='Dithering done successfully!'")

    def goFocus(self, cmd):
        if cmd.cmd.keywords["focus"].values == []:
            #dithering undefined value
            length = self.actor.slit.focus_value
        else:
            #dithering with defined value
            length = cmd.cmd.keywords["focus"].values[0]
        try:
            self.actor.slit.focus(length)
        except DeviceErr, e:
            cmd.error("text= '%s'" % e)
        except CommErr, e:
            cmd.error("text= '%s'" % e)
        except Exception, e:
            cmd.error("text= Unexpected error: '%s'" % e)
        else:
            cmd.inform("text='Focus done successfully!'")



