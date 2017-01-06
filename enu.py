KeysDictionary('enu', (1, 9),
               Key("text", String(help="text for humans")),
               Key("version", String(help="EUPS/git version")),
               Key("exptime", Float(help='exposure time in seconds')),
               Key("dateobs", String(help='absolute exposure start UTC time ISO formatted')),
               Key("slit",
                   Enum('LOADING', 'LOADED', 'INITIALISING', 'IDLE', 'BUSY', 'FAILED', name='fsm',
                        help='state machine'),
                   Enum('simulation', 'operation', name='mode', help='current mode'),
                   Float(name='X', help='x_coordinate'),
                   Float(name='Y', help='y_coordinate'),
                   Float(name='Z', help='z_coordinate'),
                   Float(name='U', help='u_coordinate'),
                   Float(name='V', help='v_coordinate'),
                   Float(name='W', help='W_coordinate'), help='slit current position'),
               Key("slitHome",
                   Float(name='X', help='x_coordinate'),
                   Float(name='Y', help='y_coordinate'),
                   Float(name='Z', help='z_coordinate'),
                   Float(name='U', help='u_coordinate'),
                   Float(name='V', help='v_coordinate'),
                   Float(name='W', help='W_coordinate'), help='slit home coordinate system'),
               Key("slitTool",
                   Float(name='X', help='x_coordinate'),
                   Float(name='Y', help='y_coordinate'),
                   Float(name='Z', help='z_coordinate'),
                   Float(name='U', help='u_coordinate'),
                   Float(name='V', help='v_coordinate'),
                   Float(name='W', help='W_coordinate'), help='slit tool coordinate system'),
               Key("slitInfo", String(help="Hexapod controller status")),

               Key("shutters",
                   Enum('LOADING', 'LOADED', 'INITIALISING', 'IDLE', 'BUSY', 'FAILED', name='fsm',
                        help='state machine'),
                   Enum('simulation', 'operation', name='mode', help='current mode'),
                   Enum('close', 'open', 'openred', 'openblue', 'undef', name='position',
                        help='shutters current position')),
               Key("shb",
                   Enum('close', 'open', name='open', help='blue shutter open bit'),
                   Enum('open', 'close', name='close', help='blue shutter close bit'),
                   Enum('ok', 'error', name='error', help='blue shutter error bit')),
               Key("shr",
                   Enum('close', 'open', name='open', help='red shutter open bit'),
                   Enum('open', 'close', name='close', help='red shutter close bit'),
                   Enum('ok', 'error', name='error', help='red shutter error bit')),

               Key("bia",
                   Enum('LOADING', 'LOADED', 'INITIALISING', 'IDLE', 'BUSY', 'FAILED', name='fsm',
                        help='state machine'),
                   Enum('simulation', 'operation', name='mode', help='current mode'),
                   Enum('off', 'on', 'undef', name='state', help='bia current state')),
               Key("biaConfig",
                   Float(name='period', help='bia illumination period'),
                   Float(name='duty', help='duty cycle')),
               Key("biaStrobe",
                   Enum('off', 'on', name='state', help='strobe mode'),

               Key("rexm",
                   Enum('LOADING', 'LOADED', 'INITIALISING', 'IDLE', 'BUSY', 'FAILED', name='fsm',
                        help='state machine'),
                   Enum('simulation', 'operation', name='mode', help='current mode'),
                   Enum('low', 'mid', 'undef', name='position', help='rexm current position')),
               Key("rexmInfo",
                   UInt(name='switchA', help='switch A state'),
                   UInt(name='switchB', help='switch B state'),
                   Int(name='speed', help='motor speed ustep/sec'),
                   Int(name='position', help='number of ustep from origin')),

               Key("temps",
                   Enum('LOADING', 'LOADED', 'INITIALISING', 'IDLE', 'BUSY', 'FAILED', name='fsm',
                        help='state machine'),
                   Enum('simulation', 'operation', name='mode', help='current mode'),
                   Float(invalid="NaN", units="C") * 8, )

               )
