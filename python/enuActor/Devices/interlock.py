
#######################################################################
#                          Interlock routine                          #
#######################################################################

def interlock(func):
    """Interlock
            print target_currPos

    Handle interlock between bia and shutter.
    In Simulation mode interlock is not handled due to redefinition of getattribute in factory
    class DualModeDevice: calls initialise from SimulationDevice in simulated mode. So interlock can't be handled.

    :raises: NotImplementedError
    """
    from functools import wraps
    @wraps(func) # for docstring
    def wrapped_func(self, *args, **kwargs):
        print self.deviceName.lower()
        if self.deviceName.lower() == 'bia':
            target_currPos = getattr(getattr(self.actor, 'shutter'), "currPos")
            if func.func_name == 'bia':
                if target_currPos == 'open' and args[0] in ['on', None]\
                        or kwargs.has_key('strobe'):
                            print("Interlock !!!")
                            return
                else:
                    return func(self, *args, **kwargs)
            else:
                raise NotImplementedError
        elif self.deviceName.lower() == 'shutter':
            target_currPos = getattr(getattr(self.actor, 'bia'), "currPos")
            if target_currPos in ['on', 'strobe', None, 'undef.']:
                print func.func_name
                if func.func_name == 'initialise':
                    print('interlock !!!')
                    return
                elif func.func_name == 'shutter':
                    if args[0] in ['open', None, "undef."]:
                        print("Interlock !!!")
                        return
                    else:
                        return func(self, *args, **kwargs)
                else:
                    raise NotImplementedError
            elif target_currPos == 'off':
                return func(self, *args, **kwargs)
            else:
                raise NotImplementedError
        else:
            raise NotImplementedError('case : %s' % self.deviceName)
    return wrapped_func
