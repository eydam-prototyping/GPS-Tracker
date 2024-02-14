from Logging import Logger
from SIM7080g import SIM7080g
import utime
import json

class GPSTrackerStateMachine:
    def __init__(self):
        """Initializes the state machine with a null state and a logger.
        """
        self.current_state = None
        self.logger = Logger("GPSTrackerStateMachine")
    
    def boot(self):
        """Boot state logic

        Actions:
        - Initialize the modem

        Transitions:
        - Transition to configuration state if successful
        - Transition to error state if unsuccessful

        """
        try:            
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
        """Configuration state logic

        Actions:
        - Load configuration from config.json
        - Connect to LTE network
        - Setup PDP context
        - Sync time
        - Setup AWS context

        Transitions:
        - Transition to Idle state if successful
        - Transition to Error state if unsuccessful
        """
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
        """Idle state logic

        Actions:
        - Sleep for camping interval
        
        Transitions:
        - Transition to track state
        - Transition to error state if unsuccessful
        """
        try:
            self.logger.debug(self.modem.at_adap._unsolicited_responses)
            utime.sleep(self.config["tracking"]["camping_interval"])
            self.transition('track')
        except Exception as e:
            self.logger.error(f"Idle error: {e}")
            self.transition('error')

    def track(self):
        """Track state logic

        Actions:
        - Turn on GNSS
        - Get GNSS position
        - Turn off GNSS
        - Connect to AWS
        - Get network info
        - Send MQTT update
        - Disconnect

        Transitions:
        - Transition to idle state
        - Transition to error state if unsuccessful
        """
        try:
            self.modem.turn_on_GNSS()
            self.modem.get_GNSS_position()
            self.modem.turn_off_GNSS()
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
        """Error state logic
        Actions:
        - Handle errors and take appropriate actions
        """
        self.logger.error("Error state. Exiting.")
        
    def transition(self, new_state):
        """Transition to a new state

        Args:
            new_state (str): The new state to transition to ('boot', 'configuration', 'idle', 'track', 'error')
        """
        try:
            self.logger.info(f"Transitioning from {self.current_state} to {new_state}")
            self.current_state = new_state
        except Exception as e:
            self.logger.error(f"Error during state transition: {e}")

    def run(self):
        """Main loop of the state machine. Runs the state machine until an error occurs or the program is terminated.
        """
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