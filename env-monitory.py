#!/usr/bin/env python3
"""
Raspberry Pi Enclosure Temperature Monitor with Fan Control
SHT30/SHT31 sensor with Home Assistant integration via MQTT

Features:
- Temperature and humidity monitoring via SHT30/SHT31
- Automatic fan control with hysteresis
- Manual fan override via MQTT/Home Assistant
- Home Assistant MQTT discovery
- Professional logging and error handling
"""

import time
import json
import logging
import signal
import sys
from datetime import datetime
from typing import Optional, Tuple

import paho.mqtt.client as mqtt
import lgpio
import board
import adafruit_sht31d

# Import configuration
try:
    import config
except ImportError:
    print("ERROR: config.py not found!")
    print("Copy config.py.template to config.py and edit with your settings")
    sys.exit(1)


class EnclosureMonitor:
    """Main monitoring class for temperature control and MQTT communication"""
    
    def __init__(self):
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # State variables
        self.fan_state = False
        self.auto_mode = True
        self.last_temp_reading = None
        self.last_humidity_reading = None
        self.fan_start_time = None
        self.running = True
        
        # Hardware setup
        self.gpio_chip = None
        self.sensor = None
        self.mqtt_client = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def setup_logging(self):
        """Configure logging based on config settings"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        # Configure root logger
        logging.basicConfig(
            level=getattr(logging, config.LOG_LEVEL),
            format=log_format,
            handlers=[]
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(console_handler)
        
        # File handler if enabled
        if config.LOG_TO_FILE:
            try:
                file_handler = logging.FileHandler(config.LOG_FILE)
                file_handler.setFormatter(logging.Formatter(log_format))
                logging.getLogger().addHandler(file_handler)
            except Exception as e:
                print(f"Warning: Could not setup file logging: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def setup_hardware(self):
        """Initialize GPIO and sensors"""
        self.logger.info("Initializing hardware...")
        
        # Setup GPIO
        try:
            self.gpio_chip = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(self.gpio_chip, config.FAN_PIN)
            self.logger.info(f"GPIO initialized, fan control on pin {config.FAN_PIN}")
        except Exception as e:
            self.logger.error(f"Failed to initialize GPIO: {e}")
            raise
        
        # Setup SHT30/SHT31 sensor
        try:
            i2c = board.I2C()
            self.sensor = adafruit_sht31d.SHT31D(i2c, address=config.I2C_ADDRESS)
            self.logger.info(f"Initialized SHT30/SHT31 sensor on I2C address 0x{config.I2C_ADDRESS:02x}")
        except Exception as e:
            self.logger.error(f"Failed to initialize SHT30/SHT31 sensor: {e}")
            raise
    
    def setup_mqtt(self):
        """Initialize MQTT connection"""
        self.logger.info(f"Connecting to MQTT broker at {config.MQTT_BROKER}:{config.MQTT_PORT}")
        
        self.mqtt_client = mqtt.Client()
        
        # Set authentication if configured
        if config.MQTT_USERNAME and config.MQTT_PASSWORD:
            self.mqtt_client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
        
        # Set callbacks
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        
        # Set will message for availability
        self.mqtt_client.will_set(
            f"{config.MQTT_TOPIC_PREFIX}/availability", 
            "offline", 
            retain=True, 
            qos=config.MQTT_QOS
        )
        
        # Connect to broker
        try:
            self.mqtt_client.connect(config.MQTT_BROKER, config.MQTT_PORT, config.MQTT_KEEPALIVE)
            self.mqtt_client.loop_start()
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            if config.ENABLE_HA_DISCOVERY:
                self.publish_ha_discovery()
            self.subscribe_to_commands()
            self.publish_initial_state()
        else:
            self.logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection"""
        if rc != 0:
            self.logger.warning("Unexpected MQTT disconnection")
    
    def on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        topic = msg.topic
        payload = msg.payload.decode()
        
        self.logger.debug(f"Received MQTT message: {topic} = {payload}")
        
        # Fan control commands
        if topic == f"{config.MQTT_TOPIC_PREFIX}/fan/set":
            if payload == "ON":
                self.auto_mode = False
                self.control_fan(True, manual=True)
            elif payload == "OFF":
                self.auto_mode = False
                self.control_fan(False, manual=True)
        
        # Auto mode control
        elif topic == f"{config.MQTT_TOPIC_PREFIX}/fan_auto/set":
            if payload == "ON":
                self.auto_mode = True
                self.logger.info("Switched to automatic mode")
            elif payload == "OFF":
                self.auto_mode = False
                self.logger.info("Switched to manual mode")
            
            self.publish_auto_mode_state()
    
    def subscribe_to_commands(self):
        """Subscribe to MQTT command topics"""
        topics = [
            f"{config.MQTT_TOPIC_PREFIX}/fan/set",
            f"{config.MQTT_TOPIC_PREFIX}/fan_auto/set"
        ]
        
        for topic in topics:
            self.mqtt_client.subscribe(topic, qos=config.MQTT_QOS)
            self.logger.debug(f"Subscribed to {topic}")
    
    def publish_ha_discovery(self):
        """Publish Home Assistant MQTT discovery configurations"""
        self.logger.info("Publishing Home Assistant discovery configurations")
        
        # Temperature sensor
        temp_config = {
            "name": "Temperature",
            "unique_id": f"{config.DEVICE_ID}_temperature",
            "state_topic": f"{config.MQTT_TOPIC_PREFIX}/temperature/state",
            "unit_of_measurement": config.TEMP_UNIT,
            "device_class": "temperature",
            "value_template": "{{ value_json.temperature }}",
            "device": config.DEVICE_INFO,
            "availability_topic": f"{config.MQTT_TOPIC_PREFIX}/availability"
        }
        
        # Humidity sensor
        humidity_config = {
            "name": "Humidity",
            "unique_id": f"{config.DEVICE_ID}_humidity",
            "state_topic": f"{config.MQTT_TOPIC_PREFIX}/humidity/state",
            "unit_of_measurement": "%",
            "device_class": "humidity",
            "value_template": "{{ value_json.humidity }}",
            "device": config.DEVICE_INFO,
            "availability_topic": f"{config.MQTT_TOPIC_PREFIX}/availability"
        }
        
        # Fan switch
        fan_config = {
            "name": "Fan",
            "unique_id": f"{config.DEVICE_ID}_fan",
            "state_topic": f"{config.MQTT_TOPIC_PREFIX}/fan/state",
            "command_topic": f"{config.MQTT_TOPIC_PREFIX}/fan/set",
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": config.DEVICE_INFO,
            "availability_topic": f"{config.MQTT_TOPIC_PREFIX}/availability"
        }
        
        # Auto mode switch
        auto_config = {
            "name": "Auto Mode",
            "unique_id": f"{config.DEVICE_ID}_auto_mode",
            "state_topic": f"{config.MQTT_TOPIC_PREFIX}/fan_auto/state",
            "command_topic": f"{config.MQTT_TOPIC_PREFIX}/fan_auto/set",
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": config.DEVICE_INFO,
            "availability_topic": f"{config.MQTT_TOPIC_PREFIX}/availability"
        }
        
        # Publish discovery messages
        discovery_prefix = "homeassistant"
        
        self.mqtt_client.publish(
            f"{discovery_prefix}/sensor/{config.DEVICE_ID}_temp/config",
            json.dumps(temp_config), retain=True, qos=config.MQTT_QOS
        )
        
        self.mqtt_client.publish(
            f"{discovery_prefix}/sensor/{config.DEVICE_ID}_humidity/config",
            json.dumps(humidity_config), retain=True, qos=config.MQTT_QOS
        )
        
        self.mqtt_client.publish(
            f"{discovery_prefix}/switch/{config.DEVICE_ID}_fan/config",
            json.dumps(fan_config), retain=True, qos=config.MQTT_QOS
        )
        
        self.mqtt_client.publish(
            f"{discovery_prefix}/switch/{config.DEVICE_ID}_auto/config",
            json.dumps(auto_config), retain=True, qos=config.MQTT_QOS
        )
    
    def publish_initial_state(self):
        """Publish initial device state"""
        # Publish availability
        self.mqtt_client.publish(
            f"{config.MQTT_TOPIC_PREFIX}/availability",
            "online", retain=True, qos=config.MQTT_QOS
        )
        
        # Publish initial fan and auto mode states
        self.mqtt_client.publish(
            f"{config.MQTT_TOPIC_PREFIX}/fan/state",
            "ON" if self.fan_state else "OFF", 
            retain=config.MQTT_RETAIN, qos=config.MQTT_QOS
        )
        
        self.publish_auto_mode_state()
    
    def publish_auto_mode_state(self):
        """Publish auto mode state"""
        self.mqtt_client.publish(
            f"{config.MQTT_TOPIC_PREFIX}/fan_auto/state",
            "ON" if self.auto_mode else "OFF", 
            retain=config.MQTT_RETAIN, qos=config.MQTT_QOS
        )
    
    def read_sensor_data(self) -> Tuple[Optional[float], Optional[float]]:
        """Read temperature and humidity from SHT30/SHT31 sensor"""
        try:
            temperature = self.sensor.temperature
            humidity = self.sensor.relative_humidity
            
            # Convert to Fahrenheit if configured
            if config.TEMP_UNIT == "°F" and temperature is not None:
                temperature = (temperature * 9/5) + 32
            
            self.last_temp_reading = temperature
            self.last_humidity_reading = humidity
            
            return temperature, humidity
            
        except Exception as e:
            self.logger.error(f"Error reading sensor: {e}")
            return None, None
    
    def control_fan(self, state: bool, manual: bool = False):
        """Control the fan state with safety checks"""
        if state == self.fan_state:
            return  # No change needed
        
        # Safety check for maximum runtime
        if state and self.fan_start_time and \
           (time.time() - self.fan_start_time) > config.FAN_MAX_RUNTIME:
            self.logger.warning("Fan maximum runtime exceeded, forcing off")
            state = False
        
        try:
            lgpio.gpio_write(self.gpio_chip, config.FAN_PIN, 1 if state else 0)
            self.fan_state = state
            
            if state:
                self.fan_start_time = time.time()
            else:
                self.fan_start_time = None
            
            control_type = "manual" if manual else "automatic"
            self.logger.info(f"Fan turned {'ON' if state else 'OFF'} ({control_type})")
            
            # Publish state to MQTT
            self.mqtt_client.publish(
                f"{config.MQTT_TOPIC_PREFIX}/fan/state",
                "ON" if state else "OFF", 
                retain=config.MQTT_RETAIN, qos=config.MQTT_QOS
            )
            
        except Exception as e:
            self.logger.error(f"Error controlling fan: {e}")
    
    def publish_sensor_data(self, temperature: Optional[float], humidity: Optional[float]):
        """Publish sensor data to MQTT"""
        if temperature is None:
            self.logger.warning("No temperature data to publish")
            return
        
        timestamp = datetime.now().isoformat()
        
        # Temperature data
        temp_data = {
            "temperature": round(temperature, 2),
            "timestamp": timestamp
        }
        
        self.mqtt_client.publish(
            f"{config.MQTT_TOPIC_PREFIX}/temperature/state",
            json.dumps(temp_data), retain=config.MQTT_RETAIN, qos=config.MQTT_QOS
        )
        
        # Humidity data
        if humidity is not None:
            humidity_data = {
                "humidity": round(humidity, 2),
                "timestamp": timestamp
            }
            
            self.mqtt_client.publish(
                f"{config.MQTT_TOPIC_PREFIX}/humidity/state",
                json.dumps(humidity_data), retain=config.MQTT_RETAIN, qos=config.MQTT_QOS
            )
        
        # Log readings
        temp_str = f"{temperature:.2f}{config.TEMP_UNIT}"
        humidity_str = f", {humidity:.1f}%" if humidity is not None else ""
        self.logger.info(f"Temperature: {temp_str}{humidity_str}, Fan: {'ON' if self.fan_state else 'OFF'}")
    
    def automatic_fan_control(self, temperature: float):
        """Handle automatic fan control based on temperature thresholds"""
        if not self.auto_mode:
            return
        
        # Check for critical temperature override
        if temperature >= config.TEMP_CRITICAL:
            if not self.fan_state:
                self.logger.warning(f"Critical temperature {temperature:.1f}{config.TEMP_UNIT} - forcing fan ON")
                self.control_fan(True)
            return
        
        # Normal automatic control
        if temperature >= config.TEMP_THRESHOLD_ON and not self.fan_state:
            self.control_fan(True)
        elif temperature <= config.TEMP_THRESHOLD_OFF and self.fan_state:
            self.control_fan(False)
    
    def run(self):
        """Main monitoring loop"""
        self.logger.info("Starting enclosure monitor...")
        
        # Startup delay if configured
        if config.STARTUP_DELAY > 0:
            self.logger.info(f"Startup delay: {config.STARTUP_DELAY} seconds")
            time.sleep(config.STARTUP_DELAY)
        
        # Initialize hardware and MQTT
        self.setup_hardware()
        self.setup_mqtt()
        
        self.logger.info("Enclosure monitor started successfully")
        
        last_publish_time = 0
        
        try:
            while self.running:
                current_time = time.time()
                
                # Read sensor data
                temperature, humidity = self.read_sensor_data()
                
                # Automatic fan control
                if temperature is not None:
                    self.automatic_fan_control(temperature)
                
                # Publish data at configured interval
                if current_time - last_publish_time >= config.PUBLISH_INTERVAL:
                    self.publish_sensor_data(temperature, humidity)
                    last_publish_time = current_time
                
                # Sleep until next reading
                time.sleep(config.UPDATE_INTERVAL)
                
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up...")
        
        # Turn off fan
        if self.gpio_chip is not None:
            try:
                lgpio.gpio_write(self.gpio_chip, config.FAN_PIN, 0)
                lgpio.gpiochip_close(self.gpio_chip)
            except Exception as e:
                self.logger.error(f"Error during GPIO cleanup: {e}")
        
        # Publish offline availability
        if self.mqtt_client is not None:
            try:
                self.mqtt_client.publish(
                    f"{config.MQTT_TOPIC_PREFIX}/availability",
                    "offline", retain=True, qos=config.MQTT_QOS
                )
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                self.logger.error(f"Error during MQTT cleanup: {e}")
        
        self.logger.info("Cleanup complete")


def main():
    """Main entry point"""
    try:
        monitor = EnclosureMonitor()
        monitor.run()
    except Exception as e:
        print(f"Failed to start enclosure monitor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()