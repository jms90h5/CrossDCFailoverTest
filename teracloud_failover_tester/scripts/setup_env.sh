#!/bin/bash
# Helper script to set up environment variables for the Teracloud Failover Tester
# Usage: source setup_env.sh

# Check if script is being sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "Error: This script must be sourced, not executed directly."
    echo "Usage: source setup_env.sh"
    exit 1
fi

# Function to prompt for environment variable
prompt_env_var() {
    local var_name="$1"
    local var_desc="$2"
    local var_default="$3"
    
    # Check if variable already set
    if [[ -z "${!var_name}" ]]; then
        # Prompt for value with optional default
        if [[ -n "$var_default" ]]; then
            read -p "$var_desc [$var_default]: " var_value
            var_value="${var_value:-$var_default}"
        else
            read -p "$var_desc: " var_value
        fi
        
        # Export the variable
        export "$var_name"="$var_value"
        echo "Export: $var_name"
    else
        echo "Using existing $var_name=${!var_name}"
    fi
}

echo "Setting up environment variables for Teracloud Failover Tester"
echo "------------------------------------------------------------"

# Primary datacenter
prompt_env_var "PRIMARY_API_TOKEN" "Primary datacenter API token"
prompt_env_var "PRIMARY_DC_URL" "Primary datacenter URL" "https://streams-api.primary-dc.example.com/v2"

# Secondary datacenter
prompt_env_var "SECONDARY_API_TOKEN" "Secondary datacenter API token"
prompt_env_var "SECONDARY_DC_URL" "Secondary datacenter URL" "https://streams-api.secondary-dc.example.com/v2"

# Optional SSH credentials for fault injection
read -p "Configure SSH credentials for fault injection? (y/n) [n]: " setup_ssh
setup_ssh="${setup_ssh:-n}"

if [[ "$setup_ssh" == "y" ]]; then
    prompt_env_var "SSH_HOST" "SSH host for fault injection"
    prompt_env_var "SSH_USER" "SSH username"
    
    read -p "Authentication type (password/key) [key]: " auth_type
    auth_type="${auth_type:-key}"
    
    if [[ "$auth_type" == "password" ]]; then
        read -sp "SSH password: " ssh_password
        echo ""
        export SSH_PASSWORD="$ssh_password"
        echo "Export: SSH_PASSWORD (hidden)"
    else
        prompt_env_var "SSH_KEY_PATH" "Path to SSH private key" "~/.ssh/id_rsa"
    fi
fi

echo ""
echo "Environment variables have been set. You can now run the tester."
echo "For example: python main.py --scenario scenarios/network_partition_test.yaml"
echo ""