import machine
import utime
from Logging import Logger
import ATadapter

class SIM7080g:
    flg_uart_initialized = False

    def __init__(self, _serial_port, _baud_rate, _rx_pin, _tx_pin, _pwr_pin):
        self.logger = Logger("SIM7080g")
        self.rx_pin = _rx_pin
        self.tx_pin = _tx_pin
        try:
            self.uart = machine.UART(_serial_port, _baud_rate, tx=_tx_pin, rx=_rx_pin)
            self.logger.info("UART interface initialized successfully.")
            self.flg_uart_initialized = True
            self.at_adap = ATadapter.Adapter(self.uart)
        except Exception as e:
            self.logger.error(f"Failed to initialize UART interface: {e}")

        self.pwr_pin = machine.Pin(_pwr_pin, machine.Pin.OUT)
        
    def power_cycle(self):
        self.pwr_pin.value(1)
        utime.sleep(2)
        self.pwr_pin.value(0)

    def initialize(self, reboot=False):
        if reboot:
            self.logger.info("Rebooting Modem")
            self.power_cycle()
            utime.sleep(5)
        
        cntr = 0

        while True:
            cmd = ATadapter.AT_command("", ATadapter.AT_CMD_TYPE_EXEC, _timeout=1000, _afterrun=1000)
            self.at_adap.queue_command(cmd)
            self.at_adap.run()
            
            if cmd.state == ATadapter.AT_CMD_STATE_TIMEOUT:
                cntr += 1
                if cntr == 10:
                    cntr = 0
                    self.logger.info("Modem not responding. Rebooting again.")
                    self.power_cycle()
                    utime.sleep(5)
            elif cmd.state == ATadapter.AT_CMD_STATE_FINISHED_00:
                if "NORMAL POWER DOWN" in self.at_adap._unsolicited_responses:
                    self.logger.info("Modem in Power Down mode. Rebooting again.")
                    self.power_cycle()
            elif cmd.state == ATadapter.AT_CMD_STATE_FINISHED:
                    self.logger.info("Modem ready.")
                    break
            
            
        cmd = ATadapter.AT_command("+CMEE", ATadapter.AT_CMD_TYPE_WRITE, "2")
        self.at_adap.queue_command(cmd)
        self.at_adap.run()
            
    def setup_LTE(self):
        at_cfun1 = ATadapter.AT_command("+CFUN", ATadapter.AT_CMD_TYPE_WRITE, "0")
        at_cnmp = ATadapter.AT_command("+CNMP", ATadapter.AT_CMD_TYPE_WRITE, "38")
        at_cfun2 = ATadapter.AT_command("+CFUN", ATadapter.AT_CMD_TYPE_WRITE, "1")
        at_cmnb = ATadapter.AT_command("+CMNB", ATadapter.AT_CMD_TYPE_WRITE, "1", _afterrun=5000)
        self.at_adap.queue_command(at_cfun1)
        self.at_adap.queue_command(at_cnmp)
        self.at_adap.queue_command(at_cfun2)
        self.at_adap.queue_command(at_cmnb)
        self.at_adap.run()
        return at_cnmp.state == ATadapter.AT_CMD_STATE_FINISHED
    
    def setup_pdp_context(self):
        at_apn1 = ATadapter.AT_command("+CGNAPN", ATadapter.AT_CMD_TYPE_EXEC)
        self.at_adap.queue_command(at_apn1)
        self.at_adap.run()
        apn1 = at_apn1.res1[0].split(",")[1]
        if apn1 == '""':
            apn1 = '"tm"'
        #at_cncfg = ATadapter.AT_command("+CNCFG", ATadapter.AT_CMD_TYPE_WRITE, "0,1," + apn1)
        at_cncfg = ATadapter.AT_command("+CNCFG", ATadapter.AT_CMD_TYPE_WRITE, "0,1")
        at_cnactw = ATadapter.AT_command("+CNACT", ATadapter.AT_CMD_TYPE_WRITE, "0,1", 3000, _afterrun=10000)
        at_cnactr = ATadapter.AT_command("+CNACT", ATadapter.AT_CMD_TYPE_READ)
        self.at_adap.queue_command(at_cncfg)
        self.at_adap.queue_command(at_cnactw)
        self.at_adap.queue_command(at_cnactr)
        self.at_adap.run()

        return at_cnactr.state == ATadapter.AT_CMD_STATE_FINISHED

    def get_manufacturer(self):
        cmd = ATadapter.AT_command("+CGMI", ATadapter.AT_CMD_TYPE_EXEC)
        self.at_adap.queue_command(cmd)
        self.at_adap.run()

        return cmd.res2[-1] if cmd.state==ATadapter.AT_CMD_STATE_FINISHED else -1
    
    def get_model(self):
        cmd = ATadapter.AT_command("+CGMM", ATadapter.AT_CMD_TYPE_EXEC)
        self.at_adap.queue_command(cmd)
        self.at_adap.run()

        return cmd.res2[-1] if cmd.state==ATadapter.AT_CMD_STATE_FINISHED else -1
    
    def get_revision(self):
        cmd = ATadapter.AT_command("+CGMR", ATadapter.AT_CMD_TYPE_EXEC)
        self.at_adap.queue_command(cmd)
        self.at_adap.run()

        return cmd.res2[-1] if cmd.state==ATadapter.AT_CMD_STATE_FINISHED else -1
    
    def get_imsi(self):
        cmd = ATadapter.AT_command("+CIMI", ATadapter.AT_CMD_TYPE_EXEC)
        self.at_adap.queue_command(cmd)
        self.at_adap.run()

        return cmd.res2[-1] if cmd.state==ATadapter.AT_CMD_STATE_FINISHED else -1
    
    def get_imei(self):
        cmd = ATadapter.AT_command("+GSN", ATadapter.AT_CMD_TYPE_EXEC)
        self.at_adap.queue_command(cmd)
        self.at_adap.run()

        return cmd.res2[-1] if cmd.state==ATadapter.AT_CMD_STATE_FINISHED else -1
    
    def get_ip_addresses(self):
        cmd = ATadapter.AT_command("+CNACT", ATadapter.AT_CMD_TYPE_READ)
        self.at_adap.queue_command(cmd)
        self.at_adap.run()

        if cmd.state == 3:
            res = []
            for ctx in cmd.res1:
                r = ctx.split(",")
                res.append({"id":r[0], "state":r[1], "ip":r[2]})
            return res
        else:
            return -1
        
    def sync_NTP_time(self, ntp_server, tz_offset):
        cmd1 = ATadapter.AT_command("+CNTP", ATadapter.AT_CMD_TYPE_WRITE, ntp_server + "," + str(4*tz_offset))
        cmd2 = ATadapter.AT_command("+CNTP", ATadapter.AT_CMD_TYPE_EXEC, _afterrun=3000)
        cclk = ATadapter.AT_command("+CCLK", ATadapter.AT_CMD_TYPE_READ)
        self.at_adap.queue_command(cmd1)
        self.at_adap.queue_command(cmd2)
        self.at_adap.queue_command(cclk)
        self.at_adap.run()

        self.logger.debug(cmd1)
        self.logger.debug(cmd2)
        self.logger.debug(cclk)

        cntp_res_code = cmd2.res1[0].split(",")
        if cntp_res_code == "61": self.logger.warning("Time sync failed: Network Error")
        elif cntp_res_code == "62": self.logger.warning("Time sync failed: DNS resolution error")
        elif cntp_res_code == "63": self.logger.warning("Time sync failed: Connection Error")
        elif cntp_res_code == "64": self.logger.warning("Time sync failed: Service response error")
        elif cntp_res_code == "65": self.logger.warning("Time sync failed: Service Response Timeout")
        else:
            t, tz = cclk.res1[0][1:-1].split("+")  # "24/01/14,18:08:32+02" --> ["24/01/14,18:08:32", "02"]
            d, t = t.split(",") # "24/01/14,18:08:32" --> ["24/01/14", "18:08:32"]
            y, mo, d = d.split("/")
            h, mi, s = t.split(":")
            machine.RTC().datetime((int(y)+2000, int(mo), int(d), 0, int(h), int(mi), int(s), 0))
        
            return cmd2.state == 3
        self.logger.warning("Failed to set Time")
        return False
    
    def setup_aws_context(self, smconf_params, csslcfg_params, smssl_params):
        for param in smconf_params:
            self.at_adap.queue_command(ATadapter.AT_command("+SMCONF", ATadapter.AT_CMD_TYPE_WRITE, param))

        for param in csslcfg_params:
            self.at_adap.queue_command(ATadapter.AT_command("+CSSLCFG", ATadapter.AT_CMD_TYPE_WRITE, param))

        for param in smssl_params:
            self.at_adap.queue_command(ATadapter.AT_command("+SMSSL", ATadapter.AT_CMD_TYPE_WRITE, param))
        
        self.at_adap.run()

    def connect_to_AWS(self):
        smconn = ATadapter.AT_command("+SMCONN", ATadapter.AT_CMD_TYPE_EXEC, _timeout=20000)

        self.at_adap.queue_command(smconn)
        self.at_adap.run()

    def disconnect_from_AWS(self):
        smdisc = ATadapter.AT_command("+SMDISC", ATadapter.AT_CMD_TYPE_EXEC)

        self.at_adap.queue_command(smdisc)
        self.at_adap.run()

    def get_network_info(self):
        at_cpsi = ATadapter.AT_command("+CPSI", ATadapter.AT_CMD_TYPE_READ)
        at_csdp = ATadapter.AT_command("+CSDP", ATadapter.AT_CMD_TYPE_READ)
        at_cgnapn = ATadapter.AT_command("+CGNAPN", ATadapter.AT_CMD_TYPE_READ)
        at_clbs = ATadapter.AT_command("+CLBS", ATadapter.AT_CMD_TYPE_WRITE, "1,0", _afterrun=1000)
        self.at_adap.queue_command(at_cpsi)
        self.at_adap.queue_command(at_csdp)
        self.at_adap.queue_command(at_cgnapn)
        self.at_adap.queue_command(at_clbs)
        self.at_adap.run()

        network_info = {}

        if at_cpsi.state == ATadapter.AT_CMD_STATE_FINISHED:
            entries = at_cpsi.res1[0].split(",")
            network_info["System Mode"] = entries[0]
            network_info["Operation Mode"] = entries[1]

            if len(entries) > 2:
                network_info["MCC-MNC"] = entries[2]

            if len(entries) == 9: # GSM
                network_info["LAC"] = entries[3]
                network_info["Cell ID"] = entries[4]
                network_info["Absolute RF Ch Num"] = entries[5]
                network_info["RxLev"] = entries[6]
                network_info["Track LO Adjust"] = entries[7]
                network_info["C1-C2"] = entries[8]

            if len(entries) == 14: # LTE
                network_info["TAC"] = entries[3]
                network_info["SCellID"] = int(entries[4])
                network_info["eNBID"] = network_info["SCellID"] >> 8
                network_info["SectorID"] = network_info["SCellID"] & 0xFF
                network_info["PCellID"] = int(entries[5]) 
                network_info["Frequency Band"] = entries[6]
                network_info["earfcn"] = int(entries[7])
                network_info["dlbw"] = int(entries[8])
                network_info["ulbw"] = int(entries[9])
                network_info["RSRQ"] = int(entries[10])
                network_info["RSRP"] = int(entries[11])
                network_info["RSSI"] = int(entries[12])
                network_info["RSSNR"] = int(entries[13])

        d = {"0":"CS Only", "2":"PS Only", "3": "CS+PS"}
        network_info["Service Domain Preference"] = "" if at_csdp.state != ATadapter.AT_CMD_STATE_FINISHED else d[at_csdp.res1[0]]
        network_info["APN"] = "" if at_cgnapn.state != ATadapter.AT_CMD_STATE_FINISHED else at_cgnapn.res1

        if at_clbs.state == ATadapter.AT_CMD_STATE_FINISHED:
            d = at_clbs.res1[0].split(",")
            if d[0] == "0":
                network_info["Basestation Longitude"] = d[1]
                network_info["Basestation Latitude"] = d[2]
                network_info["Basestation Accuracy"] = d[3]

        return network_info
    
    def send_mqtt(self, topic:str, content:str, qos:int=0, retain:int=0):
        at_smpub = ATadapter.AT_command(f"+SMPUB", ATadapter.AT_CMD_TYPE_WRITE, f'"{topic}",{len(content)},{qos},{retain}', data=content)
        self.at_adap.queue_command(at_smpub)
        self.at_adap.run()

    def turn_on_GNSS(self):
        cmd = ATadapter.AT_command(f"+CGNSPWR", ATadapter.AT_CMD_TYPE_WRITE, "1")
        self.at_adap.queue_command(cmd)
        self.at_adap.run()

    def turn_off_GNSS(self):
        cmd = ATadapter.AT_command(f"+CGNSPWR", ATadapter.AT_CMD_TYPE_WRITE, "0")
        self.at_adap.queue_command(cmd)
        self.at_adap.run()

    def get_GNSS_position(self):
        cmd = ATadapter.AT_command(f"+CGNSINF", ATadapter.AT_CMD_TYPE_EXEC)
        self.at_adap.queue_command(cmd)
        self.at_adap.run()
