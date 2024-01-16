
# GPS Tracker Project Documentation

## Project Overview
This project involves developing a GPS tracker using a Raspberry Pi Pico (RP2040) and a SIM7040G module with a built-in GPS. The device will publish its location and cell data to AWS IoT Core every 5 minutes.

## Hardware Components
- **Raspberry Pi Pico (RP2040)**: Main microcontroller.
- **SIM7040G Module**: Provides LTE connectivity and GPS functionality.
- **Battery**: Powers the device.

## Software and Connectivity
- **MicroPython**: Programming language for the Raspberry Pi Pico.
- **AWS IoT Core**: Cloud service for receiving and storing GPS data.

## State Machine Design
### States
1. **Boot State**: System initialization and hardware checks.
2. **Configuration State**: Network and MQTT setup, GPS module initialization.
3. **Idle State**: Low-power mode between data transmissions.
4. **Track State**: Active data retrieval and transmission to AWS.
5. **Error State**: Error detection and handling.

![image](docs\img\GPS-Tracker_State-Diagram.drawio.png)

## Error Handling Best Practices
- Clear identification and logging of errors.
- Graceful degradation and automated recovery.
- User notification for critical errors.
- Regular health checks for system components.

## Power Management
Implement power-saving techniques, especially in the Idle State, to extend battery life.

## Future Steps
- Testing and debugging the system.
- Designing a custom PCB integrating all components.
- Optimizing for efficient power usage and network reliability.
