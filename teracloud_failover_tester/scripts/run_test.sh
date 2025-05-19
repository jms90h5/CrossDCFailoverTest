#!/bin/bash
# Helper script to run Teracloud Failover Tests
# Usage: ./run_test.sh <scenario_name> [options]

# Default values
PYTHON_CMD="python"
CONFIG_FILE="config/config.yaml"
REPORT_FORMAT="junit"
LOG_LEVEL="INFO"
OUTPUT_DIR="results"
SKIP_CLEANUP=false

# Check if we're on RHEL or need to use python3 explicitly
if command -v python3 > /dev/null && ! command -v python > /dev/null; then
    PYTHON_CMD="python3"
fi

# Function to display help
show_help() {
    echo "Teracloud Failover Tester - Test Runner"
    echo "---------------------------------------"
    echo "Usage: ./run_test.sh <scenario_name> [options]"
    echo ""
    echo "Arguments:"
    echo "  <scenario_name>           Name of the scenario without path/extension"
    echo "                            (e.g., network_partition_test)"
    echo ""
    echo "Options:"
    echo "  -c, --config FILE         Config file (default: $CONFIG_FILE)"
    echo "  -r, --report FORMAT       Report format: junit, html, both (default: $REPORT_FORMAT)"
    echo "  -l, --log-level LEVEL     Log level: DEBUG, INFO, WARNING (default: $LOG_LEVEL)"
    echo "  -o, --output-dir DIR      Output directory (default: $OUTPUT_DIR)"
    echo "  -s, --skip-cleanup        Skip cleanup after test (default: false)"
    echo "  -h, --help                Show this help message and exit"
    echo ""
    echo "Examples:"
    echo "  ./run_test.sh network_partition_test"
    echo "  ./run_test.sh api_stop_job_test --report both --log-level DEBUG"
    echo ""
}

# Check for help flag
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

# Check if scenario name was provided
if [ -z "$1" ]; then
    echo "Error: Scenario name is required"
    show_help
    exit 1
fi

# Get scenario name and remove from arguments
SCENARIO_NAME=$1
shift

# Ensure scenario file exists
SCENARIO_FILE="scenarios/${SCENARIO_NAME}.yaml"
if [ ! -f "$SCENARIO_FILE" ]; then
    echo "Error: Scenario file not found: $SCENARIO_FILE"
    echo "Available scenarios:"
    ls -1 scenarios/*.yaml | sed 's|scenarios/||' | sed 's|.yaml$||'
    exit 1
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -r|--report)
            REPORT_FORMAT="$2"
            shift 2
            ;;
        -l|--log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        -o|--output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -s|--skip-cleanup)
            SKIP_CLEANUP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Construct command
CMD="$PYTHON_CMD main.py --scenario $SCENARIO_FILE --config $CONFIG_FILE --report $REPORT_FORMAT --log-level $LOG_LEVEL --output-dir $OUTPUT_DIR"

# Add skip-cleanup if needed
if [ "$SKIP_CLEANUP" = true ]; then
    CMD="$CMD --skip-cleanup"
fi

# Run the test
echo "Running test: $SCENARIO_NAME"
echo "Command: $CMD"
echo ""

# Execute the command
$CMD

# Get exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "Test completed successfully"
    echo "Results available in: $OUTPUT_DIR"
else
    echo ""
    echo "Test failed with exit code: $EXIT_CODE"
    echo "Check logs in: $OUTPUT_DIR"
fi

exit $EXIT_CODE