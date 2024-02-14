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

unsolicited_responses = [
    "+CRING:",
    "+CREG:",
    "+CMTI:",
    "+CMT:",
    "+CBM:",
    "+CDS:",
    "*PSNWID:",
    "*PSUTTZ:",
    "+CTZV:",
    "DST:",
    "+CPIN:",
    "NORMAL POWER DOWN",
    "UNDER-VOLTAGE POWER DOWN",
    "UNDER-VOLTAGE WARNNING",
    "OVER-VOLTAGE POWER DOWN",
    "OVER-VOLTAGE WARNNING",
    "RDY",
    "+CFUN:",
    "CONNECT",
    "CONNECT OK",
    "CONNECT FAIL",
    "ALREADY CONNECT",
    "SEND OK",
    "CLOSED",
    "RECV FROM:",
    "+IPD,",
    "+RECEIVE,",
    "REMOTE IP:",
    "+CDNSGIP:",
    "+PDP:",
    "+APP PDP:"
]


class AT_command:
    state = 0

    def __init__(self, _cmd:str, _type:int, _param:str=None, _timeout:int=1000, _afterrun:int=0, data:str=""):
        """Initializes the AT_command object

        Args:
            _cmd (str): AT command string
            _type (int): AT_CMD_TYPE_TEST, AT_CMD_TYPE_READ, AT_CMD_TYPE_WRITE, AT_CMD_TYPE_EXEC
            _param (str, optional): parameter for write commands. Defaults to None.
            _timeout (int, optional): timeout in ms. Defaults to 1000.
            _afterrun (int, optional): time to wait after command has finished. Defaults to 0.
            data (str, optional): data to be sent after command (for download or payload). Defaults to "".
        """
        
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
        """Initializes the ATAdapter

        Args:
            uart: machine.UART object
        """
        self._uart = uart
        self._poll = select.poll()
        self._poll.register(uart, select.POLLIN)
        self.logger = Logger("ATAdapter")

    def queue_command(self, command:AT_command):
        """Queues an AT command for execution

        Args:
            command (AT_command): AT command object that will be queued for execution
        """
        
        self._command_queue.append(command)
        command.state = AT_CMD_STATE_SCHEDULED

    def run(self):
        """Executes all queued AT commands in the order they were queued
        """
        for cmd in self._command_queue:
            self._execute_command(cmd)

    def _execute_command(self, cmd: AT_command):
        """Executes a single AT command

        Args:
            cmd (AT_command): The AT command to be executed
        """
        
        # if command is not scheduled, return (eg. already executed or failed)
        if cmd.state != AT_CMD_STATE_SCHEDULED:
            return
        
        # Build the AT command string
        c = "AT"+cmd.cmd

        if cmd.typ == AT_CMD_TYPE_TEST:
            c += "=?"
        
        if cmd.typ == AT_CMD_TYPE_READ:
            c += "?"
        
        if cmd.typ == AT_CMD_TYPE_WRITE:
            c += "=" + cmd.param
        
        if cmd.typ == AT_CMD_TYPE_EXEC:
            pass

        # Send the AT command to the modem (via UART)
        self._uart.write((c+"\r\n").encode("ascii"))
        cmd.state = AT_CMD_STATE_RUNNING
        self.logger.debug(">> " + c)
        t0 = utime.ticks_ms()
        t1 = 0
        
        # while state is running or running_wait and timeout or afterrun has not been reached
        while \
            ((utime.ticks_ms()-t0 < cmd.timeout) & (cmd.state == AT_CMD_STATE_RUNNING)) |  \
            ((utime.ticks_ms()-t1 < cmd.afterrun) & (cmd.state == AT_CMD_STATE_RUNNING_WAIT)) :

            # calculate timeout for poll
            if cmd.state == AT_CMD_STATE_RUNNING:
                poll_timeout = cmd.timeout-(utime.ticks_ms()-t0)
            
            # calculate timeout for afterrun
            elif cmd.state == AT_CMD_STATE_RUNNING_WAIT:
                poll_timeout = cmd.afterrun-(utime.ticks_ms()-t1)
            
            # read from uart
            events = self._poll.poll(poll_timeout)
            
            # process uart inputs
            for event in events:    
                # format and split uart input
                lines = [line.strip() for line in event[0].read().decode().split("\n") if line.strip()!=""]
                for line in lines:
                    self.logger.debug("<< " + line)

                    # skip, if line is the command itself
                    if line == c:
                        pass

                    # typical responses (starts with command)
                    elif (cmd.cmd!="") & line.startswith(cmd.cmd):
                        cmd.res1.append(line[len(cmd.cmd)+2:])
                    
                    # if line is "OK", set state to finished or running_wait (for afterrun)
                    elif line in ["OK"]:
                        if cmd.afterrun > 0:
                            cmd.state = AT_CMD_STATE_RUNNING_WAIT
                            t1 = utime.ticks_ms()
                        else:
                            cmd.state = AT_CMD_STATE_FINISHED
                        self.logger.debug(cmd)
                    
                    # if line is \x00, set state to finished_00
                    elif line in ["\x00"]:
                        cmd.state = AT_CMD_STATE_FINISHED_00
                        self.logger.debug(cmd)

                    # if line is "ERROR", set state to failed
                    elif line == "ERROR":
                        cmd.state = AT_CMD_STATE_FAILED
                        self.logger.debug(cmd)
                    
                    # if line is "DOWNLOAD" or ">", send data
                    elif line in ["DOWNLOAD",">"]:
                        for i in range(len(cmd.data)//100+1):
                            self._uart.write(cmd.data[100*i:100*(i+1)])
                            utime.sleep(0.1)
                    
                    else: 
                        self.logger.debug("++ " + line)
                        if any([line.startswith(x) for x in unsolicited_responses]):
                            self._unsolicited_responses.append(line)
                        else:
                            cmd.res2.append(line)
                        
        if cmd.state == AT_CMD_STATE_RUNNING:
            cmd.state = AT_CMD_STATE_TIMEOUT
        elif cmd.state == AT_CMD_STATE_RUNNING_WAIT:
            cmd.state = AT_CMD_STATE_FINISHED

        self.logger.info(cmd)

    def print_command_queue(self):
        """Prints the command queue
        """
        for cmd in self._command_queue:
            self.logger.info(cmd)