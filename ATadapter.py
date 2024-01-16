import utime
import select
from Logging import Logger

AT_CMD_STATE_INIT = 0
AT_CMD_STATE_SCHEDULED = 1
AT_CMD_STATE_RUNNING = 2
AT_CMD_STATE_RUNNING_WAIT = 21
AT_CMD_STATE_FINISHED = 3
AT_CMD_STATE_FINISHED_00 = 31
AT_CMD_STATE_FAILED = 4
AT_CMD_STATE_TIMEOUT = 5

AT_CMD_TYPE_TEST = 0
AT_CMD_TYPE_READ = 1
AT_CMD_TYPE_WRITE = 2
AT_CMD_TYPE_EXEC = 3

class AT_command:
    
    # 0  = init
    # 1  = queued
    # 2  = running
    # 3  = finished (OK)
    # 4  = failed (ERROR)
    # 5  = timeout
    # 6  = finisehd ([00])
    # 21 = waiting for afterrun
    state = 0

    def __init__(self, _cmd:str, _type:int, _param:str=None, _timeout:int=1000, _afterrun:int=0, data:str=""):
        self.cmd = _cmd
        self.typ = _type
        self.param = _param
        self.timeout = _timeout
        self.afterrun = _afterrun
        self.data = data
        self.res1 = []
        self.res2 = []

    def __repr__(self) -> str:
        return f"AT_command(cmd: {self.cmd}, res: {str(self.res1)}/{str(self.res2)}, state: {self.state})"

class Adapter:
    _command_queue = []
    _uart = None
    _poll = None
    _unsolicited_responses = []

    def __init__(self, uart):
        self._uart = uart
        self._poll = select.poll()
        self._poll.register(uart, select.POLLIN)
        self.logger = Logger("ATAdapter")

    def queue_command(self, command:AT_command):
        self._command_queue.append(command)
        command.state = AT_CMD_STATE_SCHEDULED

    def run(self):
        for cmd in self._command_queue:
            self._execute_command(cmd)

    def _execute_command(self, cmd: AT_command):
        if cmd.state != AT_CMD_STATE_SCHEDULED:
            return
        
        c = "AT"+cmd.cmd

        if cmd.typ == AT_CMD_TYPE_TEST:
            c += "=?"
        
        if cmd.typ == AT_CMD_TYPE_READ:
            c += "?"
        
        if cmd.typ == AT_CMD_TYPE_WRITE:
            c += "=" + cmd.param
        
        if cmd.typ == AT_CMD_TYPE_EXEC:
            pass

        self._uart.write((c+"\r\n").encode("ascii"))
        cmd.state = AT_CMD_STATE_RUNNING
        self.logger.debug(">> " + c)
        t0 = utime.ticks_ms()
        t1 = 0
        while \
            ((utime.ticks_ms()-t0 < cmd.timeout) & (cmd.state == AT_CMD_STATE_RUNNING)) |  \
            ((utime.ticks_ms()-t1 < cmd.afterrun) & (cmd.state == AT_CMD_STATE_RUNNING_WAIT)) :
            if cmd.state == AT_CMD_STATE_RUNNING:
                poll_timeout = cmd.timeout-(utime.ticks_ms()-t0)
            elif cmd.state == AT_CMD_STATE_RUNNING_WAIT:
                poll_timeout = cmd.afterrun-(utime.ticks_ms()-t1)
            events = self._poll.poll(poll_timeout)
            for event in events:
                
                lines = [line.strip() for line in event[0].read().decode().split("\n") if line.strip()!=""]
                for line in lines:
                    self.logger.debug("<< " + line)
                    if line == c:
                        pass
                    elif (cmd.cmd!="") & line.startswith(cmd.cmd):
                        cmd.res1.append(line[len(cmd.cmd)+2:])
                    elif line in ["OK"]:
                        if cmd.afterrun > 0:
                            cmd.state = AT_CMD_STATE_RUNNING_WAIT
                            t1 = utime.ticks_ms()
                        else:
                            cmd.state = AT_CMD_STATE_FINISHED
                        self.logger.debug(cmd)
                    elif line in ["\x00"]:
                        cmd.state = AT_CMD_STATE_FINISHED_00
                        self.logger.debug(cmd)
                    elif line == "ERROR":
                        cmd.state = AT_CMD_STATE_FAILED
                        self.logger.debug(cmd)
                    elif line in ["DOWNLOAD",">"]:
                        for i in range(len(cmd.data)//100+1):
                            self._uart.write(cmd.data[100*i:100*(i+1)])
                            utime.sleep(0.1)
                    else: 
                        self.logger.debug("++ " + line)
                        cmd.res2.append(line)
                        
        if cmd.state == AT_CMD_STATE_RUNNING:
            cmd.state = AT_CMD_STATE_TIMEOUT
        elif cmd.state == AT_CMD_STATE_RUNNING_WAIT:
            cmd.state = AT_CMD_STATE_FINISHED

    def print_command_queue(self):
        for cmd in self._command_queue:
            print(cmd)