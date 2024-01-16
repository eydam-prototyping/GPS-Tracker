from GPSTrackerStateMachine import GPSTrackerStateMachine

# Initialize and run the state machine
tracker = GPSTrackerStateMachine()
tracker.transition('boot')
tracker.run()