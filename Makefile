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
	@echo "$(BLUE)Raspberry Pi Enclosure Monitor$(RESET)"
	@echo "================================="
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "Quick start:"
	@echo "  1. cp $(CONFIG_TEMPLATE) $(CONFIG_FILE)"
	@echo "  2. edit $(CONFIG_FILE) with your settings"
	@echo "  3. make install"

install: check-config setup-venv ## Complete installation (creates service, enables autostart)
	@echo "$(BLUE)Installing $(PROJECT_NAME)...$(RESET)"
	
	# Create installation directory
	sudo mkdir -p $(INSTALL_DIR)
	
	# Copy files
	sudo cp -r . $(INSTALL_DIR)/
	sudo chown -R $(USER):$(USER) $(INSTALL_DIR)
	
	# Install Python dependencies
	cd $(INSTALL_DIR) && $(PIP) install -r requirements.txt
	
	# Create systemd service
	@echo "$(YELLOW)Creating systemd service...$(RESET)"
	sudo tee /etc/systemd/system/$(SERVICE_FILE) > /dev/null << 'EOF'
	[Unit]
	Description=Enclosure Temperature Monitor
	After=network.target
	StartLimitIntervalSec=0

	[Service]
	Type=simple
	Restart=always
	RestartSec=10
	User=$(USER)
	Group=$(USER)
	WorkingDirectory=$(INSTALL_DIR)
	ExecStart=$(INSTALL_DIR)/$(VENV_DIR)/bin/python $(INSTALL_DIR)/env-monitor.py
	StandardOutput=journal
	StandardError=journal

	[Install]
	WantedBy=multi-user.target
	EOF
	
	# Enable and start service
	sudo systemctl daemon-reload
	sudo systemctl enable $(SERVICE_NAME)
	sudo systemctl start $(SERVICE_NAME)
	
	@echo "$(GREEN)Installation complete!$(RESET)"
	@echo "Service status:"
	@make status

uninstall: ## Remove installation and service
	@echo "$(YELLOW)Uninstalling $(PROJECT_NAME)...$(RESET)"
	
	# Stop and disable service
	-sudo systemctl stop $(SERVICE_NAME)
	-sudo systemctl disable $(SERVICE_NAME)
	-sudo rm -f /etc/systemd/system/$(SERVICE_FILE)
	sudo systemctl daemon-reload
	
	# Remove installation directory
	-sudo rm -rf $(INSTALL_DIR)
	
	@echo "$(GREEN)Uninstallation complete!$(RESET)"

run: check-config setup-venv ## Run locally for testing (not as service)
	@echo "$(BLUE)Running $(PROJECT_NAME) locally...$(RESET)"
	@echo "Press Ctrl+C to stop"
	$(PYTHON) env-monitor.py

status: ## Show service status
	@echo "$(BLUE)Service Status:$(RESET)"
	@sudo systemctl is-active $(SERVICE_NAME) >/dev/null 2>&1 && echo "$(GREEN)Active$(RESET)" || echo "$(RED)Inactive$(RESET)"
	@echo ""
	@sudo systemctl status $(SERVICE_NAME) --no-pager -l

logs: ## View service logs (follow)
	@echo "$(BLUE)Following logs (Ctrl+C to stop):$(RESET)"
	sudo journalctl -u $(SERVICE_NAME) -f

check-config: ## Verify configuration exists and is valid
	@echo "$(BLUE)Checking configuration...$(RESET)"
	@if [ ! -f $(CONFIG_FILE) ]; then \
		echo "$(RED)Error: $(CONFIG_FILE) not found!$(RESET)"; \
		echo "$(YELLOW)Copy $(CONFIG_TEMPLATE) to $(CONFIG_FILE) and edit with your settings$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Configuration file exists$(RESET)"
	@$(PYTHON) -c "import config; print('Configuration syntax is valid')" 2>/dev/null || \
		(echo "$(RED)Error: Configuration file has syntax errors$(RESET)" && exit 1)
	@echo "$(GREEN)Configuration is valid$(RESET)"

setup-venv: ## Create Python virtual environment with uv
	@if [ ! -d $(VENV_DIR) ]; then \
		echo "$(BLUE)Creating Python virtual environment...$(RESET)"; \
		if command -v uv >/dev/null 2>&1; then \
			echo "$(GREEN)Using uv for fast environment creation$(RESET)"; \
			uv venv $(VENV_DIR); \
		else \
			echo "$(YELLOW)uv not found, using standard venv$(RESET)"; \
			python3 -m venv $(VENV_DIR); \
		fi; \
	fi

clean: ## Clean temporary files and caches
	@echo "$(BLUE)Cleaning temporary files...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.log" -delete
	@echo "$(GREEN)Cleanup complete$(RESET)"

restart: ## Restart the service
	@echo "$(BLUE)Restarting service...$(RESET)"
	sudo systemctl restart $(SERVICE_NAME)
	@make status

stop: ## Stop the service
	@echo "$(BLUE)Stopping service...$(RESET)"
	sudo systemctl stop $(SERVICE_NAME)

start: ## Start the service
	@echo "$(BLUE)Starting service...$(RESET)"
	sudo systemctl start $(SERVICE_NAME)
	@make status