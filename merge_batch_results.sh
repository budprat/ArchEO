#!/bin/bash

# ================================================================
# Merge Batch Evaluation Results
# ================================================================
# Merges log files and results_summary.json from batch evaluations
# ================================================================

WORK_DIR="/root/autodl-tmp/Earth-Agent"
RESULTS_BASE="${WORK_DIR}/evaluate_langchain"

# Model configurations: model_name:num_experiences
declare -A MODELS=(
    ["gpt5"]="19"
    ["deepseek"]="15"
    ["kimik2"]="18"
)

echo "========================================"
echo "Merging Batch Evaluation Results"
echo "========================================"
echo ""

# Function to merge results for a single model
merge_model_results() {
    local model_name=$1
    local num_exp=$2

    echo "Processing model: ${model_name} (${num_exp} experiences)"
    echo "----------------------------------------"

    # Find the model directory (should follow pattern: modelname_AP_enhanced_XXexp)
    local model_dir_pattern="${RESULTS_BASE}/${model_name}_AP_enhanced_${num_exp}exp"

    # Check if directory exists and has batch subdirectories
    if [ ! -d "${model_dir_pattern}" ]; then
        echo "  Warning: Model directory not found: ${model_dir_pattern}"
        echo "  Skipping ${model_name}"
        echo ""
        return
    fi

    # Count batch directories
    local batch_count=$(find "${model_dir_pattern}" -maxdepth 1 -type d -name "batch_*" | wc -l)

    if [ $batch_count -eq 0 ]; then
        echo "  Warning: No batch directories found in ${model_dir_pattern}"
        echo "  Skipping ${model_name}"
        echo ""
        return
    fi

    echo "  Found ${batch_count} batch directories"

    # Create merged directory name with timestamp
    local merged_dir="${model_dir_pattern}/merged_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "${merged_dir}"

    echo "  Merging to: ${merged_dir}"

    # Merge .log files
    echo "  Merging .log files..."
    local merged_log="${merged_dir}/${model_name}_AP_enhanced_langchain.log"

    # Start with opening bracket for JSON array
    echo "[" > "${merged_log}"

    local first_entry=true
    for batch_dir in $(find "${model_dir_pattern}" -maxdepth 1 -type d -name "batch_*" | sort -V); do
        local log_file="${batch_dir}/${model_name}_AP_enhanced_langchain.log"

        if [ -f "${log_file}" ]; then
            echo "    Processing: $(basename ${batch_dir})"

            # Read log file and append entries (it's a JSON lines format)
            while IFS= read -r line; do
                # Skip empty lines
                if [ -z "$line" ]; then
                    continue
                fi

                # Add comma before each entry except the first
                if [ "$first_entry" = false ]; then
                    echo "," >> "${merged_log}"
                fi
                first_entry=false

                # Append the JSON object
                echo "$line" >> "${merged_log}"
            done < "${log_file}"
        fi
    done

    # Close JSON array
    echo "" >> "${merged_log}"
    echo "]" >> "${merged_log}"

    echo "    Log file merged: ${merged_log}"

    # Merge results_summary.json files
    echo "  Merging results_summary.json files..."
    local merged_results="${merged_dir}/results_summary.json"

    # Use Python to merge JSON files properly
    python3 << EOF
import json
import glob
import os

model_dir = "${model_dir_pattern}"
merged_results = "${merged_results}"

# Collect all results
all_results = []

# Find all batch directories and their results
batch_dirs = sorted(glob.glob(os.path.join(model_dir, "batch_*")))

for batch_dir in batch_dirs:
    results_file = os.path.join(batch_dir, "results_summary.json")
    if os.path.exists(results_file):
        with open(results_file, 'r', encoding='utf-8') as f:
            batch_results = json.load(f)
            all_results.extend(batch_results)
            print(f"    Added {len(batch_results)} results from {os.path.basename(batch_dir)}")

# Sort by question_id
all_results.sort(key=lambda x: int(x['question_id']) if x['question_id'].isdigit() else 999999)

# Save merged results
with open(merged_results, 'w', encoding='utf-8') as f:
    json.dump(all_results, f, ensure_ascii=False, indent=4)

print(f"  Total results merged: {len(all_results)}")
print(f"  Merged results saved: {merged_results}")
EOF

    echo ""
}

# Process each model
for model_name in "${!MODELS[@]}"; do
    num_exp="${MODELS[$model_name]}"
    merge_model_results "$model_name" "$num_exp"
done

echo "========================================"
echo "Merge Complete!"
echo "========================================"
echo ""
echo "Merged results are saved in:"
echo "  ${RESULTS_BASE}/<model>_AP_enhanced_<N>exp/merged_*/"
echo ""
echo "Each merged directory contains:"
echo "  - <model>_AP_enhanced_langchain.log (merged log)"
echo "  - results_summary.json (merged results)"
echo "========================================"
