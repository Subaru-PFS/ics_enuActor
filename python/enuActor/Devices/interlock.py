#!/usr/bin/env python
# encoding: utf-8

#######################################################################
#                          Interlock routine                          #
#######################################################################

def interlock(func):
    """Interlock

    Inter lock between bia and shutter : Interlock = Bia on/strobe and shutter open
    It takes also in account state machine:
        * It takes the worst case scenario if device is INITIALISING or BUSY or FAILED

    :raises: NotImplementedError
    """
    from functools import wraps
    @wraps(func) # for docstring
    def wrapped_func(self, *args, **kwargs):
        if self.deviceName.lower() == 'bia':
            if self.actor.shutter.deviceStarted is False:
                return func(self, *args, **kwargs)
            shutterState = self.actor.shutter.fsm.current
            target_currPos = getattr(getattr(self.actor, 'shutter'), "currPos")
            if target_currPos in ['open', None, 'undef.']\
                    and shutterState in ['IDLE']\
                    or shutterState in ['FAILED', 'BUSY', 'INITIALISING']:
                if func.func_name == 'initialise':
                    self.warn("(┛ò__ó)┛ Interlock")
                    return
                elif func.func_name == 'bia':
                    if args[0] in ['on', None] or kwargs.has_key('strobe'):
                        self.warn('(┛ò__ó)┛ Interlock')
                        return
                    else:
                        return func(self, *args, **kwargs)
                else:
                    raise NotImplementedError('case : func= %s, dev= %s'\
                                              % (func.func_name, self.deviceName))
            else:
                return func(self, *args, **kwargs)
        elif self.deviceName.lower() == 'shutter':
            if self.actor.bia.deviceStarted is False:
                return func(self, *args, **kwargs)
            biaState = self.actor.bia.fsm.current
            target_currPos = getattr(getattr(self.actor, 'bia'), "currPos")
            if target_currPos in ['on', 'strobe', None, 'undef.']\
                    and biaState in ['IDLE']\
                    or biaState in ['FAILED', 'BUSY', 'INITIALISING']:
                if func.func_name == 'initialise':
                    self.warn('(┛ò__ó)┛ Interlock')
                    return
                elif func.func_name == 'shutter':
                    if args[0] in ['open', None, "undef."]:
                        self.warn('(┛ò__ó)┛ Interlock')
                        return
                    else:
                        return func(self, *args, **kwargs)
                    return func(self, *args, **kwargs)
                else:
                    raise NotImplementedError('case : %s' % self.deviceName)
            else:
                return func(self, *args, **kwargs)
        else:
            raise NotImplementedError('case : func= %s, dev= %s'\
                                    % (func.func_name, self.deviceName))
    return wrapped_func
