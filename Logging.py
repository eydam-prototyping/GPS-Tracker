import utime

class Logger:
    levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    def __init__(self, name, level='DEBUG'):
        self.name = name
        self.level = level

    def log(self, level, message):
        if level in self.levels and self.level_allowed(level):
            t = utime.gmtime()
            timestamp = '{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}'.format(t[0], t[1], t[2], t[3], t[4], t[5])
            log_message = f'[{timestamp}] [{level}] {self.name}: {message}'
            self.write_log(log_message)

    def debug(self, message):
        self.log('DEBUG', message)

    def info(self, message):
        self.log('INFO', message)

    def warning(self, message):
        self.log('WARNING', message)

    def error(self, message):
        self.log('ERROR', message)

    def critical(self, message):
        self.log('CRITICAL', message)

    def level_allowed(self, level):
        levels = self.levels
        return levels.index(level) >= levels.index(self.level)

    def write_log(self, message):
        # This method should be implemented to write the log to a file or other destination
        print(message)  # Placeholder for demonstration