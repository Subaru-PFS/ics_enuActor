#!/usr/bin/env lua
local ipaddress = require("ipaddress")


-- network config
local address = ipaddress.getAutoIp(0)
local port = 9000

-- override auto-ip if necessary but it should work.
if false then
    address = "127.0.0.1"
end

-- outlets config
local lnames={"neon", "hgar"}
local loutlets={ 1, 2}


return {address = address, port = port, lnames = lnames, loutlets = loutlets}