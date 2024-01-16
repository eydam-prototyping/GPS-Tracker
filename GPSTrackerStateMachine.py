from Logging import Logger
from SIM7080g import SIM7080g
import utime
import json

class GPSTrackerStateMachine:
    def __init__(self):
        # Initialize the current state to None
        self.current_state = None
        self.logger = Logger("GPSTrackerStateMachine")

    def boot(self):
        try:
            # Boot state logic
            # Perform necessary initializations and checks
            # Log successful boot
            
            self.logger.info("Initializing Modem...")
            self.modem = SIM7080g(0, 9600, 1, 0, 14)
            if not self.modem.flg_uart_initialized: self.transition("error")
            self.modem.initialize(True)

            self.logger.info("Boot successful. Transitioning to Configuration.")
            self.transition('configuration')
        except Exception as e:
            self.logger.error(f"Boot error: {e}")
            self.transition('error')

    def configuration(self):
        try:
            self.logger.info("Loading config...")
            try:
                with open("config.json", "r") as f:
                    self.config = json.load(f)
            except Exception as e:
                self.logger.error(f"failed to load config.json: {e}")
                self.transition('error')
                
            self.logger.info("Connecting Modem to LTE...")
            
            if self.modem.setup_LTE():
                self.logger.info("Successfully connected to LTE network.")
                self.logger.info("Manufacturer: " + str(self.modem.get_manufacturer()))
                self.logger.info("Model:        " + str(self.modem.get_model()))
                self.logger.info("Revision:     " + str(self.modem.get_revision()))
                self.logger.info("IMSI:         " + str(self.modem.get_imsi()))
                self.logger.info("IMEI:         " + str(self.modem.get_imei()))
            else:
                self.logger.error("Failed to connect to LTE network.")
                self.transition("error")       
            utime.sleep(5)
            self.logger.info("Setting up PDP context...")
            if self.modem.setup_pdp_context():
                self.logger.info("Successfully setup PDP context.")
                for ctx in self.modem.get_ip_addresses():
                    self.logger.info("Context ID: {:s}, state: {:s}, IP: {:s}".format(ctx["id"], ctx["state"], ctx["ip"]))
            else:
                self.logger.error("Failed to setup PDP context.")
                self.transition("error")       

            self.logger.info("Sync time...")
            if self.modem.sync_NTP_time(self.config["time"]["ntp_server"], self.config["time"]["timezone_offset"]):
                self.logger.info("Successfully sync time.")
            else:
                self.logger.error("Failed to sync time.")
                self.transition("error")       

            self.modem.setup_aws_context(
                self.config["aws_config"]["smconf"],
                self.config["aws_config"]["csslcfg"],
                self.config["aws_config"]["smssl"]
                )

            self.logger.info("Configuration successful. Transitioning to Idle.")
            self.transition('idle')
        except Exception as e:
            self.logger.error(f"Configuration error: {e}")
            self.transition('error')

    def idle(self):
        try:
            utime.sleep(self.config["tracking"]["camping_interval"])
            self.transition('track')
        except Exception as e:
            self.logger.error(f"Idle error: {e}")
            self.transition('error')

    def track(self):
        try:
            self.modem.connect_to_AWS()
            network_info = self.modem.get_network_info()
            self.modem.send_mqtt(self.config["aws_config"]["mqtt_update_topic"], 
                str({
                    "state": {
                        "reported": {
                            "network_info": network_info
                            }}}).replace("'", '"')
            )
            
            self.modem.disconnect_from_AWS()
            self.transition('idle')
        except Exception as e:
            self.logger.error(f"Track error: {e}")
            self.transition('error')

    def error(self):
        # Error state logic
        # Handle errors and take appropriate actions
        pass  # Placeholder for error handling logic

    def transition(self, new_state):
        try:
            self.logger.info(f"Transitioning from {self.current_state} to {new_state}")
            self.current_state = new_state
        except Exception as e:
            self.logger.error(f"Error during state transition: {e}")

    def run(self):
        # Main loop for the state machine
        while True:
            if self.current_state == 'boot':
                self.boot()
            elif self.current_state == 'configuration':
                self.configuration()
            elif self.current_state == 'idle':
                self.idle()
            elif self.current_state == 'track':
                self.track()
            elif self.current_state == 'error':
                self.error()
            else:
                self.logger.error(f"Unknown state: {self.current_state}")
                break  # Exit the loop if state is unknown