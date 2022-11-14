############################################ 
# 
# TCL generation of history
# 
############################################ 

# Display error and close procedure
proc DisplayErrorAndClose {socketID code APIName} {
	global tcl_argv
	if {$code != -2 && $code != -108} {
		set code2 [catch "ErrorStringGet $socketID $code strError"]
		if {$code2 != 0} {
			puts stdout "$APIName ERROR => $code - ErrorStringGet ERROR => $code2"
			set tcl_argv(0) "$APIName ERROR => $code"
		} else {
			puts stdout "$APIName $strError"
			set tcl_argv(0) "$APIName $strError"
		}
	} else {
		if {$code == -2} {
			puts stdout "$APIName ERROR => $code : TCP timeout"
			set tcl_argv(0) "$APIName ERROR => $code : TCP timeout"
		} 
		if {$code == -108} {
			puts stdout "$APIName ERROR => $code : The TCP/IP connection was closed by an administrator"
			set tcl_argv(0) "$APIName ERROR => $code :  The TCP/IP connection was closed by an administrator"
		} 
	}
	set code2 [catch "TCP_CloseSocket $socketID"] 
	return
}
# Main process 
set TimeOut 20 
set code 0 set PathName "/Admin/Config/ReadyPositionRegistration.dat"
# Open TCP socket 
OpenConnection $TimeOut socketID 
if {$socketID == -1} { 
	puts stdout "OpenConnection failed => $socketID" 
	return 
} 
# open file
set fileID [open $PathName "w" ]
# save Setpoint positon in a file
for { set i 1 } { $i <= 6 } { incr i } {
	set code [catch "GroupPositionSetpointGet $socketID HEXAPOD.$i SetpointPosition"] 
	if {$code != 0} { 
		DisplayErrorAndClose $socketID $code "GroupPositionSetpointGet" 
		return 
	} 
	puts $fileID "$SetpointPosition" 
}
# kill groupset code [catch "GroupKill $socketID HEXAPOD"] 
# delayafter 2000
# save Current posiiton in a filefor { set i 1 } { $i <= 6 } { incr i } {
	set code [catch "GroupPositionCurrentGet $socketID HEXAPOD.$i CurrentPosition"] 
	if {$code != 0} { 
		DisplayErrorAndClose $socketID $code "GroupPositionCurrentGet" 
		return 
	} 	puts $fileID "$CurrentPosition" }# File closingclose $fileID
# Close TCP socket 
TCP_CloseSocket $socketID 
