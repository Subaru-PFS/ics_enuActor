
#######################################################################
#                          Interlock routine                          #
#######################################################################

def interlock(func):
    """Interlock
            print target_currPos

    Handle interlock between bia and shutter.
    In Simulation mode interlock is not handled due to redefinition of getattribute in factory
    class DualModeDevice.

    :raises: NotImplementedError
    """
    from functools import wraps
    @wraps(func) # for docstring
    def wrapped_func(self, *args, **kwargs):
        print self.device.lower()
        if self.device.lower() == 'bia':
            target_currPos = getattr(getattr(self.actor, 'shutter'), "currPos")
            if func.func_name == 'bia':
                if target_currPos == 'open' and args[0] == 'on'\
                        or kwargs.has_key('strobe'):
                            print("Interlock !!!")
                            return
                else:
                    return func(self, *args, **kwargs)
            else:
                raise NotImplementedError
        elif self.device.lower() == 'shutter':
            target_currPos = getattr(getattr(self.actor, 'bia'), "currPos")
            if target_currPos in ['on', 'strobe']:
                print func.func_name
                if func.func_name == 'initialise':
                    print('interlock !!!')
                    return
                elif func.func_name == 'shutter':
                    if args[0] == 'open':
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
            raise NotImplementedError('case : %s' % self.device)
    return wrapped_func


