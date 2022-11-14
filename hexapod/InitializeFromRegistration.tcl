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
set code [catch "GroupInitialize $socketID HEXAPOD "] 
if {$code != 0} { 
	DisplayErrorAndClose $socketID $code "GroupInitialize" 
	return 
} 
if {[catch {open $PathName "r"} fileID]} {
    puts stderr "Could not open $PathName for reading\n"
    return
}
set AllSetpointPosition {}
for { set i 1 } { $i <= 6 } { incr i } {
	gets $fileID Chaine
	scan $Chaine %e Pos
	lappend AllSetpointPosition $Pos}
set AllCurrentPosition {}
for { set i 1 } { $i <= 6 } { incr i } {
	gets $fileID Chaine
	scan $Chaine %e Pos
	lappend AllCurrentPosition $Pos
}
# File closing
close $fileID
# delete file
file delete $PathName
set code [catch "GroupReadyAtPosition $socketID HEXAPOD $AllCurrentPosition"] 
if {$code != 0} { 
	DisplayErrorAndClose $socketID $code "GroupReadyAtPosition" 
	return 
} 
set code [catch "GroupMoveAbsolute $socketID HEXAPOD $AllSetpointPosition"] 
if {$code != 0} { 
	DisplayErrorAndClose $socketID $code "GroupMoveAbsolute" 
	return 
} 





# Close TCP socket 
TCP_CloseSocket $socketID 
