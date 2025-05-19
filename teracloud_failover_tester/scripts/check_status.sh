#!/bin/bash
# Status check script for Teracloud Failover Tester
# Usage: ./check_status.sh

# Default values
PYTHON_CMD="python"
CONFIG_FILE="config/config.yaml"

# Check if we're on RHEL or need to use python3 explicitly
if command -v python3 > /dev/null && ! command -v python > /dev/null; then
    PYTHON_CMD="python3"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo "Teracloud Failover Tester - Status Check"
echo "---------------------------------------"

# Check if Python is available
echo -n "Checking Python... "
if command -v $PYTHON_CMD > /dev/null; then
    PYTHON_VERSION=$($PYTHON_CMD --version)
    echo -e "${GREEN}$PYTHON_VERSION${NC}"
else
    echo -e "${RED}Not found${NC}"
    echo "Error: Python not found. Please install Python 3.9 or higher."
    exit 1
fi

# Check if main.py exists
echo -n "Checking main application... "
if [ -f "main.py" ]; then
    echo -e "${GREEN}Found${NC}"
else
    echo -e "${RED}Not found${NC}"
    echo "Error: main.py not found. Are you in the correct directory?"
    exit 1
fi

# Check if config file exists
echo -n "Checking configuration... "
if [ -f "$CONFIG_FILE" ]; then
    echo -e "${GREEN}Found${NC}"
else
    echo -e "${RED}Not found${NC}"
    echo "Error: Configuration file not found. Please run setup_wizard.py"
    exit 1
fi

# Check for required dependencies
echo -n "Checking Python dependencies... "
REQUIRED_MODULES=("yaml" "requests" "paramiko")
MISSING_MODULES=()

for module in "${REQUIRED_MODULES[@]}"; do
    if ! $PYTHON_CMD -c "import $module" &> /dev/null; then
        MISSING_MODULES+=("$module")
    fi
done

if [ ${#MISSING_MODULES[@]} -eq 0 ]; then
    echo -e "${GREEN}All found${NC}"
else
    echo -e "${RED}Missing: ${MISSING_MODULES[*]}${NC}"
    echo "Error: Some required dependencies are missing. Please install them using:"
    echo "pip install -r requirements.txt"
    exit 1
fi

# Check environment variables
echo "Checking environment variables..."
ENV_VARS=("PRIMARY_API_TOKEN" "SECONDARY_API_TOKEN")
MISSING_VARS=()

for var in "${ENV_VARS[@]}"; do
    echo -n "  $var... "
    if [ -z "${!var}" ]; then
        echo -e "${RED}Not set${NC}"
        MISSING_VARS+=("$var")
    else
        echo -e "${GREEN}Set${NC}"
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Warning: Some environment variables are not set. Run source scripts/setup_env.sh${NC}"
fi

# Check for test scenarios
echo -n "Checking test scenarios... "
SCENARIO_COUNT=$(find scenarios -name "*.yaml" | wc -l)
if [ $SCENARIO_COUNT -gt 0 ]; then
    echo -e "${GREEN}Found $SCENARIO_COUNT scenarios${NC}"
    echo "Available scenarios:"
    find scenarios -name "*.yaml" -printf "  %f\n" | sed 's/.yaml$//'
else
    echo -e "${RED}No scenarios found${NC}"
    echo "Error: No test scenarios found. Please create or download test scenarios."
    exit 1
fi

# Check access to datacenters (if possible)
echo "Checking datacenter access..."
if [ -n "$PRIMARY_API_TOKEN" ]; then
    # Extract primary URL from config
    PRIMARY_URL=$(grep -A2 "primary:" "$CONFIG_FILE" | grep "api_url" | cut -d':' -f2- | tr -d ' "')
    
    if [ -n "$PRIMARY_URL" ]; then
        echo -n "  Primary datacenter... "
        if curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $PRIMARY_API_TOKEN" "$PRIMARY_URL" | grep -q "20[0-9]"; then
            echo -e "${GREEN}Connected${NC}"
        else
            echo -e "${YELLOW}Connection failed${NC}"
        fi
    fi
fi

if [ -n "$SECONDARY_API_TOKEN" ]; then
    # Extract secondary URL from config
    SECONDARY_URL=$(grep -A2 "secondary:" "$CONFIG_FILE" | grep "api_url" | cut -d':' -f2- | tr -d ' "')
    
    if [ -n "$SECONDARY_URL" ]; then
        echo -n "  Secondary datacenter... "
        if curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $SECONDARY_API_TOKEN" "$SECONDARY_URL" | grep -q "20[0-9]"; then
            echo -e "${GREEN}Connected${NC}"
        else
            echo -e "${YELLOW}Connection failed${NC}"
        fi
    fi
fi

# Check if results directory exists and is writable
echo -n "Checking results directory... "
RESULTS_DIR="results"
if [ -d "$RESULTS_DIR" ]; then
    if [ -w "$RESULTS_DIR" ]; then
        echo -e "${GREEN}Found and writable${NC}"
    else
        echo -e "${YELLOW}Found but not writable${NC}"
    fi
else
    echo -e "${YELLOW}Not found${NC}"
    echo "Creating results directory..."
    mkdir -p "$RESULTS_DIR"
fi

# Summary
echo ""
echo "Status check complete"
if [ ${#MISSING_MODULES[@]} -eq 0 ] && [ ${#MISSING_VARS[@]} -eq 0 ]; then
    echo -e "${GREEN}Everything looks good. Ready to run tests.${NC}"
    echo "Suggested next steps:"
    echo "  1. Run a test: ./scripts/run_test.sh network_partition_test"
    echo "  2. View results: ls -l results/"
else
    echo -e "${YELLOW}Some issues were found. Please address them before running tests.${NC}"
fi