#!/bin/bash
# Archive review and progress files

# Create archive directory if it doesn't exist
mkdir -p archive

# Move review files to archive
mv REVIEW_PLAN.md archive/
mv REVIEW_PROGRESS.md archive/
mv REVIEW_SUMMARY.md archive/
mv RECOMMENDATIONS.md archive/
mv Design_Plan_Condensed.txt archive/
mv Implementation_Plan_Condensed.txt archive/
mv teracloud_failover_tester/README.progress.md archive/
mv teracloud_failover_tester/IMPLEMENTATION_STATUS.md archive/

echo "Original review and progress files have been archived to the 'archive' directory."
echo "Consolidated documents are now available in teracloud_failover_tester/docs:"
echo "- DESIGN_REVIEW.md - Complete design review findings"
echo "- RECOMMENDATIONS.md - Specific recommended updates"
echo "- FINAL_IMPLEMENTATION_REPORT.md - Final implementation status"