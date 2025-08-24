# Raspberry Pi Enclosure Monitor

A professional temperature monitoring and fan control system for Raspberry Pi enclosures, with Home Assistant integration via MQTT.

## Features

- **Temperature & Humidity Monitoring**: Uses SHT30/SHT31 sensor via I2C
- **Automatic Fan Control**: Temperature-based fan control with hysteresis to prevent oscillation
- **Manual Override**: Control fan manually via Home Assistant or MQTT
- **Home Assistant Integration**: Auto-discovery creates entities automatically
- **Professional Installation**: One-command installation with systemd service
- **Robust Error Handling**: Comprehensive logging and graceful error recovery
- **Safety Features**: Maximum runtime limits and critical temperature overrides

## Hardware Requirements

### Components
- Raspberry Pi (tested on Pi 5)
- SHT30 or SHT31 temperature/humidity sensor
- 12V DC fan (60mm or larger)
- MOSFET module (IRF520 or similar, 3.3V logic compatible)
- 12V power supply (PoE hat recommended)

### Wiring Diagram

```
SHT30/SHT31 Sensor:
  VCC → Pi 3.3V (Pin 1)
  GND → Pi Ground (Pin 6)
  SDA → Pi GPIO 2 (Pin 3)
  SCL → Pi GPIO 3 (Pin 5)

MOSFET Module:
  VCC → Pi 3.3V (Pin 17)
  GND → Pi Ground (Pin 20)
  SIG → Pi GPIO 18 (Pin 12)

Power Connections:
  12V Supply → MOSFET V+ input
  Ground → MOSFET V- input
  Fan + → MOSFET V+ output
  Fan - → MOSFET V- output
```

## Installation

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/pi-enclosure-monitor.git
   cd pi-enclosure-monitor
   ```

2. **Configure your settings**:
   ```bash
   cp config.py.template config.py
   nano config.py  # Edit with your MQTT broker and preferences
   ```

3. **Install and start**:
   ```bash
   make install
   ```

That's it! The service will be running and start automatically on boot.

### Manual Installation Steps

If you prefer to understand each step:

1. **Enable I2C** (if not already enabled):
   ```bash
   sudo raspi-config
   # Interface Options → I2C → Enable
   ```

2. **Install dependencies**:
   ```bash
   # Install uv for faster Python environment setup (optional)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Or use standard Python venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Test the configuration**:
   ```bash
   make check-config
   ```

4. **Test locally**:
   ```bash
   make run
   ```

5. **Install as service**:
   ```bash
   make install
   ```

## Configuration

Edit `config.py` to customize your installation. Key settings:

### MQTT Settings
```python
MQTT_BROKER = "mqtt.home"  # Your MQTT broker IP/hostname
MQTT_USERNAME = None       # Set if authentication required
MQTT_PASSWORD = None
```

### Temperature Control
```python
TEMP_THRESHOLD_ON = 30.0   # Fan turns ON at this temperature (°C)
TEMP_THRESHOLD_OFF = 25.0  # Fan turns OFF at this temperature (°C)
TEMP_CRITICAL = 45.0       # Emergency override temperature
```

### Hardware
```python
FAN_PIN = 18              # GPIO pin for fan control
I2C_ADDRESS = 0x44        # SHT30/SHT31 I2C address
```

## Home Assistant Integration

### Automatic Discovery

When enabled, the monitor automatically creates these entities in Home Assistant:

- `sensor.{hostname}_temperature` - Current temperature
- `sensor.{hostname}_humidity` - Current humidity
- `switch.{hostname}_fan` - Manual fan control
- `switch.{hostname}_auto_mode` - Auto/manual mode toggle

### Dashboard Card

Add this to your Home Assistant dashboard:

```yaml
type: entities
title: Enclosure Monitor
entities:
  - entity: sensor.raspberrypi_temperature
  - entity: sensor.raspberrypi_humidity
  - entity: switch.raspberrypi_fan
  - entity: switch.raspberrypi_auto_mode
```

Or use the included card template:
```bash
cat homeassistant-card.yaml
```

## Management Commands

The Makefile provides convenient management:

```bash
make help          # Show all available commands
make status        # Check service status
make logs          # View live logs
make restart       # Restart the service
make stop          # Stop the service
make start         # Start the service
make uninstall     # Remove everything
make clean         # Clean temp files
```

## Operation Modes

### Automatic Mode (Default)
- Fan turns ON when temperature ≥ `TEMP_THRESHOLD_ON`
- Fan turns OFF when temperature ≤ `TEMP_THRESHOLD_OFF`
- Hysteresis prevents rapid cycling

### Manual Mode
- Activated when you manually control the fan via Home Assistant
- Temperature thresholds are ignored
- Critical temperature override still active for safety

### Safety Features
- **Maximum Runtime**: Fan automatically shuts off after configured time
- **Critical Override**: Fan turns on regardless of mode if temperature is critical
- **Graceful Shutdown**: Fan turns off cleanly on service stop

## Troubleshooting

### Service Won't Start

Check the service status:
```bash
make status
make logs
```

Common issues:
- **I2C not enabled**: Run `sudo raspi-config` and enable I2C
- **Sensor not found**: Check wiring and I2C address
- **GPIO permissions**: Make sure user has GPIO access
- **MQTT connection**: Verify broker settings in config.py

### Sensor Reading Errors

Check I2C connection:
```bash
sudo i2cdetect -y 1
# Should show device at 0x44 (or your configured address)
```

Test sensor directly:
```bash
# In your venv
python3 -c "
import board
import adafruit_sht31d
i2c = board.I2C()
sensor = adafruit_sht31d.SHT31D(i2c)
print(f'Temp: {sensor.temperature:.2f}°C, Humidity: {sensor.relative_humidity:.2f}%')
"
```

### Fan Not Working

- Check MOSFET wiring and power connections
- Verify GPIO pin configuration matches hardware
- Test GPIO manually:
  ```bash
  # Turn fan on
  echo "18" > /sys/class/gpio/export
  echo "out" > /sys/class/gpio/gpio18/direction
  echo "1" > /sys/class/gpio/gpio18/value
  
  # Turn fan off
  echo "0" > /sys/class/gpio/gpio18/value
  echo "18" > /sys/class/gpio/unexport
  ```

### MQTT Issues

Test MQTT connection:
```bash
# Install mosquitto clients
sudo apt install mosquitto-clients

# Subscribe to your topics
mosquitto_sub -h your-broker -t "homeassistant/sensor/+/+/state"

# Publish test message
mosquitto_pub -h your-broker -t "homeassistant/sensor/test/fan/set" -m "ON"
```

### Home Assistant Not Discovering

- Check MQTT integration is configured in Home Assistant
- Verify discovery prefix matches (default: `homeassistant`)
- Look for discovery messages in MQTT logs
- Restart Home Assistant after first discovery

## Development

### Project Structure
```
pi-enclosure-monitor/
├── Makefile                 # Automation commands
├── README.md               # This documentation
├── requirements.txt        # Python dependencies
├── config.py.template      # Configuration template
├── env-monitor.py         # Main application
├── homeassistant-card.yaml # HA dashboard card
└── .gitignore             # Git ignore patterns
```

### Adding Features

The code is structured for easy extension:

- **New sensors**: Modify the sensor reading methods
- **Additional MQTT topics**: Add to discovery configuration
- **Custom controls**: Extend the MQTT message handler
- **Monitoring**: Add health checks and statistics

### Testing

Run locally for development:
```bash
make run
```

This runs the monitor in the foreground with full logging.

## RF Considerations

For SDR or RF-sensitive environments:

### Hardware Placement
- Keep MOSFET module away from antennas
- Use twisted pair wiring for all connections
- Add ferrite chokes on fan power cables
- Position sensor away from switching circuits

### Fan Selection
- Use brushless DC fans (less RF noise)
- Consider server-grade fans for better airflow
- Add RF filtering on fan power if needed

### Shielding
- Copper tape around sensitive components
- Braided cable sleeves for wire runs
- Common ground point for all shields

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Support

- **Issues**: Use GitHub issues for bugs and feature requests
- **Discussions**: Use GitHub discussions for questions
- **Documentation**: Check the wiki for additional guides

## Changelog

### v1.0.0
- Initial release
- SHT30/SHT31 sensor support
- Home Assistant MQTT discovery
- Automatic and manual fan control
- Professional installation system
- Comprehensive error handling