#!/bin/bash
# Cleanup script for Teracloud Failover Tester
# Usage: ./cleanup.sh [options]

# Default values
RESULTS_DIR="results"
KEEP_LATEST=5
KEEP_DAYS=30
DRY_RUN=false

# Function to display help
show_help() {
    echo "Teracloud Failover Tester - Cleanup Utility"
    echo "-----------------------------------------"
    echo "Usage: ./cleanup.sh [options]"
    echo ""
    echo "Options:"
    echo "  -d, --dir DIR         Results directory (default: $RESULTS_DIR)"
    echo "  -n, --keep-latest N   Keep latest N test results (default: $KEEP_LATEST)"
    echo "  -t, --keep-days N     Keep results newer than N days (default: $KEEP_DAYS)"
    echo "  --dry-run             Show what would be deleted without deleting"
    echo "  -h, --help            Show this help message and exit"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dir)
            RESULTS_DIR="$2"
            shift 2
            ;;
        -n|--keep-latest)
            KEEP_LATEST="$2"
            shift 2
            ;;
        -t|--keep-days)
            KEEP_DAYS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if results directory exists
if [ ! -d "$RESULTS_DIR" ]; then
    echo "Results directory not found: $RESULTS_DIR"
    exit 1
fi

# Count total test result directories
TOTAL_DIRS=$(find "$RESULTS_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)
echo "Found $TOTAL_DIRS test result directories"

# Identify directories to delete
DELETE_DIRS=""

# Keep results newer than specified days
if [ "$KEEP_DAYS" -gt 0 ]; then
    echo "Keeping results newer than $KEEP_DAYS days"
    OLD_DIRS=$(find "$RESULTS_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +$KEEP_DAYS)
    DELETE_DIRS="$OLD_DIRS"
fi

# Keep latest N result directories
if [ "$KEEP_LATEST" -gt 0 ]; then
    echo "Keeping latest $KEEP_LATEST test results"
    
    # Get all directories sorted by modification time (newest first)
    ALL_DIRS=$(find "$RESULTS_DIR" -mindepth 1 -maxdepth 1 -type d -printf "%T@ %p\n" | sort -nr | cut -d' ' -f2-)
    
    # Get directories to keep (latest N)
    KEEP_DIRS=$(echo "$ALL_DIRS" | head -n $KEEP_LATEST)
    
    # Get directories to delete (all except latest N)
    if [ "$TOTAL_DIRS" -gt "$KEEP_LATEST" ]; then
        LATEST_DELETE_DIRS=$(echo "$ALL_DIRS" | tail -n +$((KEEP_LATEST + 1)))
        DELETE_DIRS="$DELETE_DIRS $LATEST_DELETE_DIRS"
    fi
fi

# Combine and deduplicate the list of directories to delete
DELETE_DIRS=$(echo "$DELETE_DIRS" | tr ' ' '\n' | sort | uniq)

# Count directories to delete
DELETE_COUNT=$(echo "$DELETE_DIRS" | grep -v "^$" | wc -l)

# Display what will be deleted
if [ "$DELETE_COUNT" -gt 0 ]; then
    echo "Will delete $DELETE_COUNT result directories"
    
    # If dry run, just show what would be deleted
    if [ "$DRY_RUN" = true ]; then
        echo "DRY RUN - nothing will be deleted"
        echo "Directories that would be deleted:"
        echo "$DELETE_DIRS"
    else
        # Delete directories
        echo "Deleting..."
        echo "$DELETE_DIRS" | while read -r dir; do
            # Skip empty lines
            if [ -n "$dir" ]; then
                echo "  Removing $dir"
                rm -rf "$dir"
            fi
        done
        echo "Cleanup complete"
    fi
else
    echo "No directories to delete"
fi