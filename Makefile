# Raspberry Pi Enclosure Monitor - Makefile
# Professional automation for installation and management

SHELL := /bin/bash
PROJECT_NAME := enclosure-monitor
SERVICE_NAME := enclosure-monitor
INSTALL_DIR := /opt/$(PROJECT_NAME)
SERVICE_FILE := $(SERVICE_NAME).service
CONFIG_FILE := config.py
CONFIG_TEMPLATE := config.py.template
VENV_DIR := venv
PYTHON := $(VENV_DIR)/bin/python
PIP := $(VENV_DIR)/bin/pip

# Colors for output
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
RESET := \033[0m

.PHONY: help install uninstall run status logs clean check-config setup-venv

# Default target
help: ## Show this help message
	@echo "Raspberry Pi Enclosure Monitor"
	@echo "================================="
	@echo ""
	@echo "Available commands:"
	@echo "  help            Show this help message"
	@echo "  install         Complete installation (creates service, enables autostart)"
	@echo "  uninstall       Remove installation and service"
	@echo "  run             Run locally for testing (not as service)"
	@echo "  status          Show service status"
	@echo "  logs            View service logs (follow)"
	@echo "  restart         Restart the service"
	@echo "  start           Start the service"
	@echo "  stop            Stop the service"
	@echo "  check-config    Verify configuration exists and is valid"
	@echo "  setup-venv      Create Python virtual environment with uv"
	@echo "  clean           Clean temporary files and caches"
	@echo ""
	@echo "Quick start:"
	@echo "  1. cp config.py.template config.py"
	@echo "  2. edit config.py with your settings"
	@echo "  3. make install"

install: setup-venv check-config ## Complete installation (creates service, enables autostart)
	@echo "Installing $(PROJECT_NAME)..."
	
	# Create installation directory
	sudo mkdir -p $(INSTALL_DIR)
	
	# Copy files (excluding local venv)
	sudo rsync -av --exclude='venv' --exclude='*.pyc' --exclude='__pycache__' . $(INSTALL_DIR)/
	sudo chown -R $(USER):$(USER) $(INSTALL_DIR)
	
	# Create fresh virtual environment in installation directory
	@echo "Creating virtual environment in installation directory..."
	cd $(INSTALL_DIR) && python3 -m venv $(VENV_DIR)
	
	# Install Python dependencies in new venv
	cd $(INSTALL_DIR) && $(VENV_DIR)/bin/pip install -r requirements.txt
	
	@echo "Creating systemd service..."
	@echo "[Unit]" | sudo tee /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "Description=Enclosure Temperature Monitor" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "After=network.target" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "StartLimitIntervalSec=0" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "[Service]" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "Type=simple" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "Restart=always" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "RestartSec=10" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "User=$(USER)" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "Group=$(USER)" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "WorkingDirectory=$(INSTALL_DIR)" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "ExecStart=$(INSTALL_DIR)/$(VENV_DIR)/bin/python $(INSTALL_DIR)/env-monitor.py" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "StandardOutput=journal" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "StandardError=journal" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "[Install]" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	@echo "WantedBy=multi-user.target" | sudo tee -a /etc/systemd/system/$(SERVICE_FILE) > /dev/null
	
	
	# Enable and start service
	sudo systemctl daemon-reload
	sudo systemctl enable $(SERVICE_NAME)
	sudo systemctl start $(SERVICE_NAME)
	
	@echo "Installation complete!"
	@echo "Service status:"
	@make status

uninstall: ## Remove installation and service
	@printf "$(YELLOW)Uninstalling $(PROJECT_NAME)...$(RESET)\n"
	
	# Stop and disable service
	-sudo systemctl stop $(SERVICE_NAME)
	-sudo systemctl disable $(SERVICE_NAME)
	-sudo rm -f /etc/systemd/system/$(SERVICE_FILE)
	sudo systemctl daemon-reload
	
	# Remove installation directory
	-sudo rm -rf $(INSTALL_DIR)
	
	@printf "$(GREEN)Uninstallation complete!$(RESET)\n"

run: check-config setup-venv ## Run locally for testing (not as service)
	@printf "$(BLUE)Running $(PROJECT_NAME) locally...$(RESET)\n"
	@printf "Press Ctrl+C to stop\n"
	$(PYTHON) env-monitor.py

status: ## Show service status
	@printf "$(BLUE)Service Status:$(RESET)\n"
	@sudo systemctl is-active $(SERVICE_NAME) >/dev/null 2>&1 && printf "$(GREEN)Active$(RESET)\n" || printf "$(RED)Inactive$(RESET)\n"
	@printf "\n"
	@sudo systemctl status $(SERVICE_NAME) --no-pager -l

logs: ## View service logs (follow)
	@printf "$(BLUE)Following logs (Ctrl+C to stop):$(RESET)\n"
	sudo journalctl -u $(SERVICE_NAME) -f

check-config: setup-venv ## Verify configuration exists and is valid
	@echo "Checking configuration..."
	@if [ ! -f $(CONFIG_FILE) ]; then \
		echo "Error: $(CONFIG_FILE) not found!"; \
		echo "Copy $(CONFIG_TEMPLATE) to $(CONFIG_FILE) and edit with your settings"; \
		exit 1; \
	fi
	@echo "Configuration file exists"
	@$(PYTHON) -c "import config; print('Configuration syntax is valid')" 2>/dev/null || \
		(echo "Error: Configuration file has syntax errors" && exit 1)
	@echo "Configuration is valid"

setup-venv: ## Create Python virtual environment with uv
	@if [ ! -d $(VENV_DIR) ]; then \
		printf "$(BLUE)Creating Python virtual environment...$(RESET)\n"; \
		if command -v uv >/dev/null 2>&1; then \
			printf "$(GREEN)Using uv for fast environment creation$(RESET)\n"; \
			uv venv $(VENV_DIR); \
		else \
			printf "$(YELLOW)uv not found, using standard venv$(RESET)\n"; \
			python3 -m venv $(VENV_DIR); \
		fi; \
	fi

clean: ## Clean temporary files and caches
	@printf "$(BLUE)Cleaning temporary files...$(RESET)\n"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.log" -delete
	@printf "$(GREEN)Cleanup complete$(RESET)\n"

restart: ## Restart the service
	@printf "$(BLUE)Restarting service...$(RESET)\n"
	sudo systemctl restart $(SERVICE_NAME)
	@make status

stop: ## Stop the service
	@printf "$(BLUE)Stopping service...$(RESET)\n"
	sudo systemctl stop $(SERVICE_NAME)

start: ## Start the service
	@printf "$(BLUE)Starting service...$(RESET)\n"
	sudo systemctl start $(SERVICE_NAME)
	@make status