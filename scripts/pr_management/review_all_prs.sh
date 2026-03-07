#!/bin/bash
# Enhanced PR Management Script
# This script runs the enhanced PR orchestrator to:
# 1. Review all open PRs
# 2. Auto-merge safe PRs
# 3. Add helpful comments to uncertain PRs
# 4. Generate comprehensive reports

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default values
DRY_RUN=true
AUTO_REVIEW_ONLY=false
CONFIG_FILE="config.yaml"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --live)
            DRY_RUN=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --auto-review-only)
            AUTO_REVIEW_ONLY=true
            shift
            ;;
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --help)
            cat << EOF
Enhanced PR Management Script

Usage: $0 [OPTIONS]

OPTIONS:
    --live              Run in live mode (actually merge PRs and add comments)
    --dry-run           Run in dry-run mode (default - no actual changes)
    --auto-review-only  Run only the auto-review phase
    --config FILE       Use specific configuration file (default: config.yaml)
    --help              Show this help message

EXAMPLES:
    $0                          # Dry run with full orchestration
    $0 --live                   # Live run with full orchestration  
    $0 --auto-review-only       # Dry run with auto-review only
    $0 --live --auto-review-only # Live run with auto-review only

SAFETY:
    - The script runs in DRY-RUN mode by default for safety
    - Use --live only when you're confident in the configuration
    - Check generated reports before running in live mode
    - Auto-merge is limited to 5 PRs per run by default

EOF
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Display configuration
echo "====================================================================="
echo "🤖 Enhanced PR Management System"
echo "====================================================================="
print_status "Mode: $([ "$DRY_RUN" = true ] && echo "DRY-RUN (safe)" || echo "LIVE (actual changes)")"
print_status "Scope: $([ "$AUTO_REVIEW_ONLY" = true ] && echo "Auto-review only" || echo "Full orchestration")"
print_status "Config: $CONFIG_FILE"
echo "====================================================================="

# Safety confirmation for live mode
if [ "$DRY_RUN" = false ]; then
    print_warning "⚠️  LIVE MODE - This will make actual changes to PRs!"
    echo "This will:"
    echo "  - Automatically merge qualifying PRs"
    echo "  - Add comments to PRs that need attention"
    echo "  - Approve PRs before merging"
    echo ""
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Operation cancelled by user"
        exit 0
    fi
fi

# Check if configuration file exists
if [ ! -f "$CONFIG_FILE" ]; then
    print_error "Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Check if Python dependencies are installed
print_status "Checking dependencies..."
if ! python3 -c "import requests, yaml, tabulate" 2>/dev/null; then
    print_warning "Installing required dependencies..."
    pip install -r requirements.txt || {
        print_error "Failed to install dependencies"
        exit 1
    }
fi

# Generate timestamp for output files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_DIR="reports"
mkdir -p "$OUTPUT_DIR"

RESULTS_FILE="$OUTPUT_DIR/pr_management_results_$TIMESTAMP.json"
REPORT_FILE="$OUTPUT_DIR/pr_management_report_$TIMESTAMP.md"

# Build command
CMD="python3 enhanced_pr_orchestrator.py"
CMD="$CMD --config $CONFIG_FILE"
CMD="$CMD --output $RESULTS_FILE"
CMD="$CMD --report-file $REPORT_FILE"

if [ "$DRY_RUN" = true ]; then
    CMD="$CMD --dry-run"
else
    CMD="$CMD --live"
fi

if [ "$AUTO_REVIEW_ONLY" = true ]; then
    CMD="$CMD --auto-review-only"
fi

# Run the enhanced orchestrator
print_status "Starting PR management process..."
echo "Command: $CMD"
echo "====================================================================="

if eval "$CMD"; then
    print_success "PR management completed successfully!"
    echo ""
    print_status "Generated files:"
    echo "  📊 Results: $RESULTS_FILE"
    echo "  📋 Report:  $REPORT_FILE"
    echo ""
    
    # Display quick summary if report exists
    if [ -f "$REPORT_FILE" ]; then
        print_status "Quick Summary:"
        echo "-------------------------------------------------------------------"
        grep -A 10 "## 📊 Executive Summary" "$REPORT_FILE" || true
        echo "-------------------------------------------------------------------"
    fi
    
    if [ "$DRY_RUN" = true ]; then
        print_warning "This was a DRY RUN - no actual changes were made"
        print_status "To make actual changes, run with --live flag"
    else
        print_success "Live run completed - changes have been made to PRs"
        print_status "Please verify the results and monitor CI/CD pipelines"
    fi
    
else
    print_error "PR management failed! Check the logs above for details."
    exit 1
fi

echo "====================================================================="
print_status "For detailed information, check:"
echo "  📊 $RESULTS_FILE"
echo "  📋 $REPORT_FILE"
echo "====================================================================="